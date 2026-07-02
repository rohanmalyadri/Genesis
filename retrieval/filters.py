from pydantic import BaseModel, field_validator
from typing import Optional, List
import re

class FilterParams(BaseModel):
    """
    Filter parameters for document retrieval.
    Allows filtering by date range, source type, and specific entities.
    """
    date_gte: Optional[str] = None
    date_lte: Optional[str] = None
    source_type: Optional[str] = None # e.g., 'pdf', 'web', 'doc'
    entity_names: Optional[List[str]] = None
    document_id: Optional[str] = None
    authority_mode: bool = False

    @field_validator('date_gte', 'date_lte')
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^\d{4}-\d{2}-\d{2}', v):
            raise ValueError('Date must be in ISO format (YYYY-MM-DD...)')
        return v
