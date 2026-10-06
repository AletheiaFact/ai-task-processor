# Triage with Jev

The `defining_impact_area` and `defining_severity` tasks can run on **Jev**, TypeSafe's
evaluation model, instead of OpenAI. Jev does not generate text: it receives a state (the VR
text) and typed questions, and returns calibrated probabilities. The triage flow does not
change: `embedding → identifying_data → topics → impact_area → severity`, with the same tasks
and callbacks.

## Model routing

The backend picks the model in `task.content.model`:

| `content.model` | Provider |
|---|---|
| starts with `jev` (e.g. `jev-1.13.0`) | Jev, through the TypeSafe API |
| anything else (e.g. `o3`) | OpenAI, as before |

The version is pinned in the backend so results are reproducible: a new Jev version can shift
the probabilities the rubric depends on. Rolling back is switching the backend model back to an
OpenAI one.

## Impact area

Jev answers one **choice** question over `content.options`, the closed list of area names the
backend sends. It sees only the VR text (truncated to 6,000 characters).

```json
{
  "text": "VR content",
  "model": "jev-1.13.0",
  "options": ["Segurança Pública", "Saúde", "Política", "...", "Outros"]
}
```

- Without `options`, the task fails: Jev needs the list to choose from.
- The result keeps the existing format: `name` (one of the options), `description` (empty),
  `wikidataId` (from the usual Wikidata enrichment) and `language`.
- The OpenAI prompt also requires one of `content.options` when the backend sends them.

## Severity

Jev answers three questions about the VR text only. The questions are in English; the VR text
and the impact area options stay in Portuguese.

| Question | Type | Meaning |
|---|---|---|
| `harm` | score, 4 levels | Harm if the content were false: Low, Medium, High, Critical |
| `contestable` | boolean | Has at least one doubtful claim (no clear source, rumor, dubious data) |
| `checkable` | boolean | Has at least one specific factual claim that can be checked |

Fixed code in `services/jev_rubric.py` turns the answers into a `SeverityEnum` value:

1. **Priority matrix:** no checkable claim → Low. Otherwise, harm × contestable:

   | Harm | Contestable | Not contestable |
   |---|---|---|
   | Low | Low | Low |
   | Medium | Medium | Low |
   | High | High | Medium |
   | Critical | Critical | High |

2. **Reach matrix:** adjusts the band by −1, 0 or +1 from the followers of the personalities
   (Wikidata). Uses the personality with the most followers; missing data (0 followers or no
   Wikidata ID) is unknown reach, so no adjustment. **Neutral for now** (`REACH_THRESHOLDS = []`):
   thresholds will be defined with the fact-checkers. Not applied when nothing is checkable.
3. **Limit:** the band stays between Low and Critical.
4. **Sub-band:** compares the expected harm score with the most likely harm level. More than 1/6
   below → `_1`, more than 1/6 above → `_3`, otherwise `_2`. Critical is always `critical`.

| Band | SeverityEnum |
|---|---|
| Low | `low_1`, `low_2`, `low_3` |
| Medium | `medium_1`, `medium_2`, `medium_3` |
| High | `high_1`, `high_2`, `high_3` |
| Critical | `critical` |

The impact area does not affect the severity on Jev: the area comes from the same text, and the
harm question already considers the subject. The Wikidata enrichment of personalities, topics
and impact area is unchanged and still feeds the OpenAI prompt.

Any change to the questions, matrices or thresholds must bump `RUBRIC_VERSION`.

## OpenAI fallback

Implemented in `services/jev_fallback.py`.

- **Only temporary errors fall back:** 429, 5xx and timeouts, after the Jev retries
  (`JEV_BACKOFF_SECONDS`). The same task then runs the OpenAI path with `JEV_FALLBACK_MODEL`.
- **Other errors never fall back:** 401, 403 and 400 mean Jev is misconfigured, so the task
  fails right away.
- **Daily cap:** at most `JEV_FALLBACK_MAX_PER_DAY` fallbacks per day (UTC), shared by impact
  area and severity and stored in the rate limit SQLite database. Past the cap the task fails.
  `0` disables the fallback.
- `JEV_FALLBACK_MODEL` must be an OpenAI model; a Jev model fails the task.

## Mock mode

Same rule as OpenAI: `TYPESAFE_API_KEY=your_typesafe_api_key_here` returns mock answers in the
real format, with no API calls. Mock answers are deterministic per text (the same text always
gets the same answer) and vary across texts, so the whole flow after Jev runs for real.
Mock results are logged as a warning and reported with `model: "jev-mock"`.

An empty or missing key fails the task, so production never stores mock results.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TYPESAFE_API_KEY` | none | TypeSafe API key; the placeholder enables mock mode |
| `JEV_BASE_URL` | `https://api.typesafe.ai` | Overrides the TypeSafe API URL |
| `JEV_TIMEOUT` | `30` | Request timeout in seconds |
| `JEV_BACKOFF_SECONDS` | `[5,10,20,40,60]` | Waits between retries on 429/5xx/timeout |
| `JEV_FALLBACK_MODEL` | `o3` | OpenAI model used on fallback |
| `JEV_FALLBACK_MAX_PER_DAY` | `50` | Daily fallback cap (UTC); `0` disables the fallback |

## Observability

**Metrics:**

```prometheus
jev_requests_total{model, status}       # success, retry, retries_exhausted, error, mock
jev_tokens_used_total{model, type}      # input_tokens, output_tokens
triage_provider_total{task_type, provider}  # jev, openai_fallback, fallback_limit_reached, jev_error
```

**Logs:**

- `Jev classified impact area`: chosen area and its confidence.
- `Jev classified severity`: every step of the calculation (`harm_probabilities`,
  `harm_confidence`, `checkable_probability`, `contestable_probability`, `harm_band`,
  `matrix_band`, `reach_adjustment`, `band`, `sub_band`, `severity`, `rubric_version`) and
  whether the text was truncated.
- `Jev failed, falling back to OpenAI` and
  `Jev failed and the OpenAI fallback is disabled or over its daily limit`.

## Known limitations

- **No circuit breaker for Jev:** while Jev is down, every task still goes through all retries
  (up to about 2 min 15 s) before falling back or failing.
- **Personalities are the people mentioned in the text**, not the author of the claim, so the
  reach matrix measures who is talked about, not who spreads the claim.
- **Impact area options come only in Portuguese.**
