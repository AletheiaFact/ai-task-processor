#!/usr/bin/env python3
"""
Test script for Wikidata integration in identifying_data processor.
Tests the personality identification and enrichment workflow.
"""

import asyncio
import sys
from ai_task_processor.services.wikidata_client import wikidata_client
from ai_task_processor.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def test_search_person():
    """Test searching for a person in Wikidata"""
    print("\n" + "="*80)
    print("TEST 1: Search for a person in Wikidata")
    print("="*80)

    test_names = [
        "Luiz Inácio Lula da Silva",
        "Jair Bolsonaro",
        "Barack Obama",
        "Albert Einstein"
    ]

    for name in test_names:
        print(f"\nSearching for: {name}")
        try:
            results = await wikidata_client.search_person(name, limit=3)
            print(f"  Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"    {i}. {result.get('label')} ({result.get('id')})")
                print(f"       Description: {result.get('description', 'N/A')}")
                print(f"       URL: {result.get('url', 'N/A')}")
        except Exception as e:
            print(f"  ERROR: {e}")


async def test_enrich_personality():
    """Test enriching a personality with Wikidata"""
    print("\n" + "="*80)
    print("TEST 2: Enrich personality with Wikidata")
    print("="*80)

    test_personalities = [
        {"name": "Luiz Inácio Lula da Silva", "mentioned_as": "Lula"},
        {"name": "Jair Bolsonaro", "mentioned_as": "Bolsonaro"},
        {"name": "Unknown Person", "mentioned_as": "unknown"}
    ]

    for personality in test_personalities:
        print(f"\nEnriching: {personality['name']} (mentioned as: {personality['mentioned_as']})")
        try:
            wikidata_info = await wikidata_client.enrich_personality(
                name=personality["name"],
                mentioned_as=personality["mentioned_as"]
            )

            if wikidata_info:
                print(f"  ✓ Successfully enriched")
                print(f"    ID: {wikidata_info.get('id')}")
                print(f"    Label: {wikidata_info.get('label')}")
                print(f"    Description: {wikidata_info.get('description', 'N/A')}")
                print(f"    URL: {wikidata_info.get('url')}")
                if wikidata_info.get('aliases'):
                    print(f"    Aliases: {', '.join(wikidata_info.get('aliases', []))}")
            else:
                print(f"  ✗ No Wikidata match found")
        except Exception as e:
            print(f"  ERROR: {e}")


async def test_batch_enrich():
    """Test batch enrichment of personalities"""
    print("\n" + "="*80)
    print("TEST 3: Batch enrich multiple personalities")
    print("="*80)

    personalities = [
        {
            "name": "Luiz Inácio Lula da Silva",
            "mentioned_as": "Lula",
            "confidence": 0.95,
            "context": "Former president of Brazil"
        },
        {
            "name": "Jair Bolsonaro",
            "mentioned_as": "Bolsonaro",
            "confidence": 0.90,
            "context": "Current president"
        },
        {
            "name": "Dilma Rousseff",
            "mentioned_as": "Dilma",
            "confidence": 0.88,
            "context": "Former president"
        }
    ]

    print(f"\nEnriching {len(personalities)} personalities in parallel...")
    try:
        enriched = await wikidata_client.batch_enrich_personalities(personalities)

        print(f"\n✓ Batch enrichment completed")
        for i, person in enumerate(enriched, 1):
            print(f"\n  {i}. {person['name']}")
            if person.get('wikidata'):
                wd = person['wikidata']
                print(f"     Wikidata ID: {wd.get('id')}")
                print(f"     URL: {wd.get('url')}")
                print(f"     Description: {wd.get('description', 'N/A')}")
            else:
                print(f"     ✗ No Wikidata match")
    except Exception as e:
        print(f"  ERROR: {e}")


async def test_full_integration():
    """Test the complete integration flow"""
    print("\n" + "="*80)
    print("TEST 4: Full integration test (mock AI + Wikidata enrichment)")
    print("="*80)

    # Simulate output from AI model
    mock_ai_result = {
        "personalities": [
            {
                "name": "Luiz Inácio Lula da Silva",
                "mentioned_as": "Lula",
                "confidence": 0.95,
                "context": "The text mentions Lula as a former president"
            },
            {
                "name": "Marina Silva",
                "mentioned_as": "Marina",
                "confidence": 0.85,
                "context": "Marina is mentioned as an environmental activist"
            }
        ],
        "model": "o3-mini",
        "usage": {"prompt_tokens": 50, "total_tokens": 50}
    }

    print("\nMock AI identified personalities:")
    for p in mock_ai_result["personalities"]:
        print(f"  - {p['name']} (as '{p['mentioned_as']}', confidence: {p['confidence']})")

    print("\nEnriching with Wikidata...")
    try:
        enriched_personalities = await wikidata_client.batch_enrich_personalities(
            personalities=mock_ai_result["personalities"],
            language="en"
        )

        print("\n✓ Enrichment completed")
        print("\nFinal result:")
        for i, person in enumerate(enriched_personalities, 1):
            print(f"\n{i}. {person['name']}")
            print(f"   Mentioned as: {person['mentioned_as']}")
            print(f"   Confidence: {person['confidence']}")

            if person.get('wikidata'):
                wd = person['wikidata']
                print(f"   Wikidata:")
                print(f"     - ID: {wd.get('id')}")
                print(f"     - Label: {wd.get('label')}")
                print(f"     - Description: {wd.get('description', 'N/A')}")
                print(f"     - URL: {wd.get('url')}")
            else:
                print(f"   Wikidata: Not found")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("WIKIDATA INTEGRATION TEST SUITE")
    print("="*80)

    try:
        await test_search_person()
        await test_enrich_personality()
        await test_batch_enrich()
        await test_full_integration()

        print("\n" + "="*80)
        print("ALL TESTS COMPLETED")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up HTTP session
        await wikidata_client.close()


if __name__ == "__main__":
    asyncio.run(main())
