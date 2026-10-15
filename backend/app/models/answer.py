"""Answer domain models for user responses to clarification questions."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class Answer(BaseModel):
    """User response submitted for a clarification question.

    Attributes:
        id: Unique identifier for the answer.
        project_id: Identifier of the parent project.
        question_id: Identifier of the answered question.
        value: Textual or selected response value.
        answered_at: Timestamp when the response was provided.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique answer identifier")
    project_id: str = Field(..., description="Associated project ID")
    question_id: str = Field(..., description="ID of the question being answered")
    value: str = Field(..., description="Answer text or selected value")
    answered_at: datetime = Field(
        ...,
        description="Timestamp when the answer was recorded",
    )
