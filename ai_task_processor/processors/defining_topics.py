from typing import Dict, Any
from ..models import Task, TaskResult, TaskStatus, TaskType, DefiningTopicsInput
from ..services.defining_services import defining_topics
from ..services.wikidata_client import wikidata_client
from ..utils import get_logger, RetryableError
from ..config import settings
from .base_processor import BaseProcessor

logger = get_logger(__name__)


class DefiningTopicsProcessor(BaseProcessor):
    def can_process(self, task: Task) -> bool:
        result = task.type == TaskType.DEFINING_TOPICS
        logger.info(
            "DefiningTopicsProcessor can_process check",
            task_id=task.id,
            task_type=task.type,
            expected_type=TaskType.DEFINING_TOPICS,
            can_process=result
        )
        return result

    async def process(self, task: Task) -> TaskResult:
        try:
            logger.info(
                "Starting DefiningTopicsProcessor.process",
                task_id=task.id,
                task_type=task.type,
                content_type=type(task.content),
                content_value=task.content
            )

            if not task.content:
                raise ValueError("Task content is missing or None")

            # Handle different content formats
            if isinstance(task.content, str):
                default_model = settings.supported_models[0] if settings.supported_models else "o3-mini"
                input_data = DefiningTopicsInput(
                    text=task.content,
                    model=default_model
                )
                logger.warning(
                    "Task content is string format, using default supported model",
                    task_id=task.id,
                    default_model=input_data.model
                )
            elif isinstance(task.content, dict):
                if "model" not in task.content:
                    raise ValueError("Model is required in task content")
                input_data = DefiningTopicsInput(**task.content)
            else:
                raise ValueError(f"Unsupported content type: {type(task.content)}")

            # Validate that the requested model is supported
            if not defining_topics.supports_model(input_data.model):
                raise ValueError(
                    f"Requested model '{input_data.model}' is not supported. "
                    f"Supported models: {settings.supported_models}"
                )

            logger.info(
                "Processing defining topics task",
                task_id=task.id,
                text_length=len(input_data.text),
                model=input_data.model
            )

            # Use the defining topics provider to identify topics
            result = await defining_topics.define_topics(
                text=input_data.text,
                model=input_data.model,
                correlation_id=task.id
            )

            logger.info(
                "Identified topics from AI model",
                task_id=task.id,
                topics_count=len(result.get("topics", [])),
                correlation_id=task.id
            )

            topics_from_ai = result.get("topics", [])
            final_topics = []

            logger.info(
                "Processing topics and enriching with Wikidata",
                task_id=task.id,
                topics_count=len(topics_from_ai),
                correlation_id=task.id
            )

            for topic in topics_from_ai:
                name = topic.get("name", "")
                wikidata_id = None

                if name:
                    try:
                        wikidata_info = await wikidata_client.enrich_topic(
                            topic=name,
                            language="pt",
                            correlation_id=task.id
                        )

                        if wikidata_info:
                            wikidata_id = wikidata_info.get("id", "")
                            logger.info(
                                "Topic enriched with Wikidata",
                                task_id=task.id,
                                topic_name=name,
                                wikidata_id=wikidata_id,
                                correlation_id=task.id
                            )
                        else:
                            logger.warning(
                                "No Wikidata found for topic",
                                task_id=task.id,
                                topic_name=name,
                                correlation_id=task.id
                            )

                    except Exception as e:
                        logger.warning(
                            "Failed to enrich topic with Wikidata",
                            task_id=task.id,
                            topic_name=name,
                            error=str(e),
                            correlation_id=task.id
                        )

                topic_payload = {
                    "name": name,
                    "wikidataId": wikidata_id,
                    "language": "pt"
                }

                final_topics.append(topic_payload)

            enriched_count = sum(1 for t in final_topics if t.get("wikidataId"))
            logger.info(
                "Topics processing completed successfully",
                task_id=task.id,
                total_topics=len(final_topics),
                enriched_count=enriched_count,
                correlation_id=task.id
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.SUCCEEDED,
                output_data=final_topics
            )

        except RetryableError as e:
            logger.warning(
                "Defining topics processing failed with retryable error",
                task_id=task.id,
                error=str(e)
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Retryable error: {str(e)}"
            )

        except Exception as e:
            logger.error(
                "Defining topics processing failed",
                task_id=task.id,
                error=str(e)
            )

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error_message=f"Defining topics failed: {str(e)}"
            )
