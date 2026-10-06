from pydantic import BaseModel, Field


class Rule(BaseModel):
    on: bool = True
    value: float = Field(..., ge=0, le=365)


class RiskRules(BaseModel):
    attendance_below: Rule = Rule(value=75)  # overall attendance below this %
    attendance_drop: Rule = Rule(value=10)  # fell by at least this many points in the last 4 weeks
    marks_below: Rule = Rule(value=40)  # below this % of the marks in any published internal assessment
    backlogs: Rule = Rule(value=1)  # at least this many subjects still to clear
    fee_overdue: Rule = Rule(value=30)  # an installment overdue for at least this many days


class NoteIn(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000)
    follow_up_on: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class AssignIn(BaseModel):
    mentor_id: str | None = Field(None, description="None removes the mentor")
    student_ids: list[str] = Field(..., min_length=1, max_length=200)
