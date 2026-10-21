import pytest
from pydantic import ValidationError

from app.schemas import AnalysisRequest


def test_empty_chemical_input_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest(chemical_input="")
