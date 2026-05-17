import csv
import io
import json
import os
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./atomquest.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


engine = create_engine(
    database_url(),
    connect_args={"check_same_thread": False} if database_url().startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Role(str, Enum):
    employee = "employee"
    manager = "manager"
    admin = "admin"


class SheetStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    returned = "returned"
    approved = "approved"


class UomType(str, Enum):
    numeric = "numeric"
    percent = "percent"
    timeline = "timeline"
    zero = "zero"


class Direction(str, Enum):
    min = "min"
    max = "max"
    none = "none"


class ProgressStatus(str, Enum):
    not_started = "Not Started"
    on_track = "On Track"
    completed = "Completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), index=True)
    department: Mapped[str] = mapped_column(String(120))
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    manager: Mapped[Optional["User"]] = relationship(remote_side=[id])


class Cycle(Base):
    __tablename__ = "cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    active_phase: Mapped[str] = mapped_column(String(30), default="goal_setting")
    active_quarter: Mapped[str] = mapped_column(String(10), default="Q1")
    window_open_month: Mapped[str] = mapped_column(String(40), default="May")


class GoalSheet(Base):
    __tablename__ = "goal_sheets"
    __table_args__ = (UniqueConstraint("employee_id", "cycle_id", name="uq_employee_cycle"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("cycles.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=SheetStatus.draft.value)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    returned_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    employee: Mapped[User] = relationship(foreign_keys=[employee_id])
    cycle: Mapped[Cycle] = relationship()
    goals: Mapped[list["Goal"]] = relationship(cascade="all, delete-orphan", back_populates="sheet")


class SharedGoalGroup(Base):
    __tablename__ = "shared_goal_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    thrust_area: Mapped[str] = mapped_column(String(120))
    uom_type: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(20))
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    primary_owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("goal_sheets.id"), index=True)
    thrust_area: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    uom_type: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(20), default=Direction.min.value)
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weightage: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default=ProgressStatus.not_started.value)
    shared_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shared_goal_groups.id"), nullable=True)
    is_primary_owner: Mapped[bool] = mapped_column(Boolean, default=False)

    sheet: Mapped[GoalSheet] = relationship(back_populates="goals")
    achievements: Mapped[list["Achievement"]] = relationship(cascade="all, delete-orphan", back_populates="goal")


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("goal_id", "quarter", name="uq_goal_quarter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id"), index=True)
    quarter: Mapped[str] = mapped_column(String(10), index=True)
    actual_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=ProgressStatus.not_started.value)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    goal: Mapped[Goal] = relationship(back_populates="achievements")


class CheckIn(Base):
    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("sheet_id", "quarter", name="uq_sheet_quarter_checkin"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("goal_sheets.id"), index=True)
    quarter: Mapped[str] = mapped_column(String(10), index=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str] = mapped_column(Text)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(120))
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    actor: Mapped[User] = relationship()


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20))
    event_type: Mapped[str] = mapped_column(String(80))
    recipient_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    deep_link: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EscalationLog(Base):
    __tablename__ = "escalation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(20))
    subject_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    escalated_to_role: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subject_user: Mapped[User] = relationship()


PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://atomquest-goaltrack-portal.onrender.com")
ENTRA_GROUP_ROLE_MAP = {
    "GoalTrack-Admins": Role.admin.value,
    "GoalTrack-Managers": Role.manager.value,
    "GoalTrack-Employees": Role.employee.value,
}


class GoalIn(BaseModel):
    id: Optional[int] = None
    thrust_area: str
    title: str
    description: str
    uom_type: UomType
    direction: Direction = Direction.min
    target_value: Optional[float] = None
    deadline: Optional[date] = None
    weightage: float = Field(ge=0, le=100)


class AchievementIn(BaseModel):
    quarter: str
    actual_value: Optional[float] = None
    completion_date: Optional[date] = None
    status: ProgressStatus
    comment: Optional[str] = None


class ManagerGoalPatch(BaseModel):
    target_value: Optional[float] = None
    deadline: Optional[date] = None
    weightage: Optional[float] = Field(default=None, ge=10, le=100)


class ReturnIn(BaseModel):
    reason: str


class CheckInIn(BaseModel):
    quarter: str
    comment: str = Field(min_length=5)


class CyclePatch(BaseModel):
    active_phase: str
    active_quarter: str
    window_open_month: str


class SharedGoalIn(BaseModel):
    title: str
    description: str
    thrust_area: str
    uom_type: UomType
    direction: Direction = Direction.min
    target_value: Optional[float] = None
    deadline: Optional[date] = None
    primary_owner_id: int
    recipient_employee_ids: list[int]
    weightage: float = Field(ge=10, le=100)


class UnlockIn(BaseModel):
    reason: str


class EntraSsoIn(BaseModel):
    email: str


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(
    db: Session = Depends(db_session),
    x_user_email: str = Header(default="admin@atomberg.demo"),
) -> User:
    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unknown demo user")
    return user


def require_role(*roles: Role):
    def guard(user: User = Depends(current_user)) -> User:
        if user.role not in {role.value for role in roles}:
            raise HTTPException(status_code=403, detail="Insufficient role permissions")
        return user

    return guard


def active_cycle(db: Session) -> Cycle:
    cycle = db.query(Cycle).first()
    if not cycle:
        raise HTTPException(status_code=500, detail="No active cycle configured")
    return cycle


def sheet_for_employee(db: Session, employee_id: int) -> GoalSheet:
    cycle = active_cycle(db)
    sheet = (
        db.query(GoalSheet)
        .filter(GoalSheet.employee_id == employee_id, GoalSheet.cycle_id == cycle.id)
        .first()
    )
    if not sheet:
        sheet = GoalSheet(employee_id=employee_id, cycle_id=cycle.id)
        db.add(sheet)
        db.commit()
        db.refresh(sheet)
    return sheet


def as_dict(model: Any, fields: list[str]) -> dict[str, Any]:
    return {field: getattr(model, field) for field in fields}


def audit(db: Session, actor: User, entity_type: str, entity_id: int, action: str, before: Any, after: Any) -> None:
    db.add(
        AuditLog(
            actor_id=actor.id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=json.dumps(before, default=str),
            after_json=json.dumps(after, default=str),
        )
    )


def portal_deep_link(email: str, sheet_id: Optional[int] = None) -> str:
    link = f"{PORTAL_BASE_URL}/?email={email}"
    if sheet_id is not None:
        link += f"&sheet={sheet_id}"
    return link


def entra_groups_for_user(user: User) -> list[str]:
    if user.role == Role.admin.value:
        return ["GoalTrack-Admins", "All-Staff"]
    if user.role == Role.manager.value:
        return ["GoalTrack-Managers", "All-Staff"]
    return ["GoalTrack-Employees", "All-Staff"]


def queue_notification(
    db: Session,
    *,
    channel: str,
    event_type: str,
    recipient: User,
    subject: str,
    body: str,
    sheet_id: Optional[int] = None,
) -> None:
    db.add(
        NotificationLog(
            channel=channel,
            event_type=event_type,
            recipient_email=recipient.email,
            subject=subject,
            body=body,
            deep_link=portal_deep_link(recipient.email, sheet_id),
            status="queued",
        )
    )


def notify_workflow_event(db: Session, event_type: str, sheet: GoalSheet, actor: User) -> None:
    employee = sheet.employee
    manager = employee.manager
    if event_type == "goal_submitted" and manager:
        queue_notification(
            db,
            channel="email",
            event_type=event_type,
            recipient=manager,
            subject=f"Goal sheet submitted by {employee.name}",
            body=f"{employee.name} submitted a goal sheet for approval.",
            sheet_id=sheet.id,
        )
        queue_notification(
            db,
            channel="teams",
            event_type=event_type,
            recipient=manager,
            subject=f"Teams: {employee.name} submitted goals",
            body=f"Adaptive card: review {employee.name}'s goal sheet in GoalTrack.",
            sheet_id=sheet.id,
        )
    elif event_type == "goal_approved":
        queue_notification(
            db,
            channel="email",
            event_type=event_type,
            recipient=employee,
            subject="Your goal sheet was approved",
            body=f"{actor.name} approved and locked your goal sheet.",
            sheet_id=sheet.id,
        )
    elif event_type == "goal_returned":
        queue_notification(
            db,
            channel="email",
            event_type=event_type,
            recipient=employee,
            subject="Goal sheet returned for rework",
            body=sheet.returned_reason or "Please update your goals and resubmit.",
            sheet_id=sheet.id,
        )
    elif event_type == "checkin_completed":
        queue_notification(
            db,
            channel="teams",
            event_type=event_type,
            recipient=employee,
            subject=f"Check-in completed by {actor.name}",
            body="Your manager recorded a quarterly check-in comment.",
            sheet_id=sheet.id,
        )


def cycle_created_at(_db: Session, _cycle: Cycle) -> datetime:
    return datetime.utcnow() - timedelta(days=10)


def run_escalation_scan(db: Session) -> list[EscalationLog]:
    created: list[EscalationLog] = []
    cycle = active_cycle(db)
    now = datetime.utcnow()
    sheets = db.query(GoalSheet).filter(GoalSheet.cycle_id == cycle.id).all()

    def add_escalation(rule_code: str, user: User, role: str, message: str, severity: str = "medium") -> None:
        exists = (
            db.query(EscalationLog)
            .filter(EscalationLog.rule_code == rule_code, EscalationLog.subject_user_id == user.id, EscalationLog.status == "open")
            .first()
        )
        if exists:
            return
        row = EscalationLog(
            rule_code=rule_code,
            severity=severity,
            subject_user_id=user.id,
            escalated_to_role=role,
            message=message,
            status="open",
        )
        db.add(row)
        created.append(row)
        hr = db.query(User).filter(User.role == Role.admin.value).first()
        if hr:
            queue_notification(db, channel="email", event_type="escalation", recipient=hr, subject=f"Escalation: {rule_code}", body=message)

    for sheet in sheets:
        employee = sheet.employee
        manager = employee.manager
        if sheet.status == SheetStatus.draft.value and (now - cycle_created_at(db, cycle)) > timedelta(days=7):
            add_escalation(
                "employee_goal_not_submitted",
                employee,
                Role.manager.value,
                f"{employee.name} has not submitted goals within 7 days of cycle open.",
                "high",
            )
        if sheet.status == SheetStatus.submitted.value and sheet.submitted_at and (now - sheet.submitted_at) > timedelta(days=5):
            if manager:
                add_escalation(
                    "manager_approval_overdue",
                    manager,
                    Role.admin.value,
                    f"{manager.name} has not approved {employee.name}'s sheet within 5 days of submission.",
                    "high",
                )
        if sheet.status == SheetStatus.approved.value:
            active_q = cycle.active_quarter
            has_checkin = db.query(CheckIn).filter(CheckIn.sheet_id == sheet.id, CheckIn.quarter == active_q).first()
            if not has_checkin and sheet.approved_at and (now - sheet.approved_at) > timedelta(days=14):
                if manager:
                    add_escalation(
                        "checkin_not_completed",
                        manager,
                        Role.admin.value,
                        f"{active_q} check-in pending for {employee.name}.",
                        "medium",
                    )
    db.flush()
    return created


def build_org_hierarchy(db: Session) -> list[dict[str, Any]]:
    users = db.query(User).all()
    nodes: dict[int, dict[str, Any]] = {}
    for user in users:
        nodes[user.id] = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "department": user.department,
            "manager_id": user.manager_id,
            "entra_groups": entra_groups_for_user(user),
            "reports": [],
        }
    roots: list[dict[str, Any]] = []
    for user in users:
        node = nodes[user.id]
        if user.manager_id and user.manager_id in nodes:
            nodes[user.manager_id]["reports"].append(node)
        else:
            roots.append(node)
    return roots


def advanced_analytics(db: Session) -> dict[str, Any]:
    employees = db.query(User).filter(User.role == Role.employee.value).all()
    goals = db.query(Goal).all()
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    qoq_trends: list[dict[str, Any]] = []
    for quarter in quarters:
        scores = [
            progress_score(goal, achievement)
            for goal in goals
            for achievement in goal.achievements
            if achievement.quarter == quarter
        ]
        qoq_trends.append(
            {
                "quarter": quarter,
                "avg_progress": round(sum(scores) / len(scores), 1) if scores else 0,
                "goals_tracked": len(scores),
            }
        )

    department_heatmap: list[dict[str, Any]] = []
    departments = sorted({employee.department for employee in employees})
    for department in departments:
        dept_employees = [employee for employee in employees if employee.department == department]
        approved = submitted = 0
        for employee in dept_employees:
            sheet = sheet_for_employee(db, employee.id)
            if sheet.status == SheetStatus.approved.value:
                approved += 1
            if sheet.status == SheetStatus.submitted.value:
                submitted += 1
        total = len(dept_employees) or 1
        department_heatmap.append(
            {
                "department": department,
                "approved_rate": round(approved / total * 100, 1),
                "submitted_rate": round(submitted / total * 100, 1),
                "headcount": len(dept_employees),
            }
        )

    uom_counts: dict[str, int] = {}
    for goal in goals:
        uom_counts[goal.uom_type] = uom_counts.get(goal.uom_type, 0) + 1

    return {
        "qoq_trends": qoq_trends,
        "department_heatmap": department_heatmap,
        "uom_distribution": [{"name": key, "value": value} for key, value in uom_counts.items()],
    }


def validate_goal_payload(goals: list[GoalIn], require_total: bool = False) -> None:
    if len(goals) > 8:
        raise HTTPException(status_code=422, detail="A goal sheet can contain at most 8 goals")
    for goal in goals:
        if goal.weightage < 10:
            raise HTTPException(status_code=422, detail="Each goal must have at least 10% weightage")
        if goal.uom_type in {UomType.numeric, UomType.percent} and goal.target_value is None:
            raise HTTPException(status_code=422, detail=f"Goal '{goal.title}' requires a numeric target")
        if goal.uom_type == UomType.timeline and goal.deadline is None:
            raise HTTPException(status_code=422, detail=f"Goal '{goal.title}' requires a deadline")
    if require_total and round(sum(goal.weightage for goal in goals), 2) != 100:
        raise HTTPException(status_code=422, detail="Total goal weightage must equal exactly 100%")


def validate_sheet(sheet: GoalSheet) -> None:
    goals = [
        GoalIn(
            id=goal.id,
            thrust_area=goal.thrust_area,
            title=goal.title,
            description=goal.description,
            uom_type=goal.uom_type,
            direction=goal.direction,
            target_value=goal.target_value,
            deadline=goal.deadline,
            weightage=goal.weightage,
        )
        for goal in sheet.goals
    ]
    validate_goal_payload(goals, require_total=True)


def progress_score(goal: Goal, achievement: Optional[Achievement]) -> float:
    if not achievement:
        return 0.0
    if goal.uom_type == UomType.zero.value:
        return 100.0 if (achievement.actual_value or 0) == 0 else 0.0
    if goal.uom_type == UomType.timeline.value:
        if not achievement.completion_date or not goal.deadline:
            return 0.0
        return 100.0 if achievement.completion_date <= goal.deadline else 50.0
    if not goal.target_value or not achievement.actual_value:
        return 0.0
    ratio = achievement.actual_value / goal.target_value
    if goal.direction == Direction.max.value:
        ratio = goal.target_value / achievement.actual_value
    return round(max(0.0, min(ratio * 100, 150.0)), 2)


def serialize_goal(goal: Goal, quarter: Optional[str] = None) -> dict[str, Any]:
    achievement = None
    if quarter:
        achievement = next((item for item in goal.achievements if item.quarter == quarter), None)
    latest = achievement or (sorted(goal.achievements, key=lambda item: item.updated_at)[-1] if goal.achievements else None)
    return {
        "id": goal.id,
        "thrust_area": goal.thrust_area,
        "title": goal.title,
        "description": goal.description,
        "uom_type": goal.uom_type,
        "direction": goal.direction,
        "target_value": goal.target_value,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "weightage": goal.weightage,
        "status": goal.status,
        "shared_group_id": goal.shared_group_id,
        "is_primary_owner": goal.is_primary_owner,
        "read_only_shared_fields": bool(goal.shared_group_id and not goal.is_primary_owner),
        "achievement": {
            "quarter": latest.quarter,
            "actual_value": latest.actual_value,
            "completion_date": latest.completion_date.isoformat() if latest.completion_date else None,
            "status": latest.status,
            "comment": latest.comment,
            "progress_score": progress_score(goal, latest),
        }
        if latest
        else None,
    }


def serialize_sheet(sheet: GoalSheet, quarter: Optional[str] = None) -> dict[str, Any]:
    weighted_score = 0.0
    goals = [serialize_goal(goal, quarter) for goal in sheet.goals]
    for goal, payload in zip(sheet.goals, goals):
        score = payload["achievement"]["progress_score"] if payload["achievement"] else 0.0
        weighted_score += score * (goal.weightage / 100)
    return {
        "id": sheet.id,
        "employee": {
            "id": sheet.employee.id,
            "name": sheet.employee.name,
            "email": sheet.employee.email,
            "department": sheet.employee.department,
        },
        "status": sheet.status,
        "locked": sheet.locked,
        "returned_reason": sheet.returned_reason,
        "submitted_at": sheet.submitted_at.isoformat() if sheet.submitted_at else None,
        "approved_at": sheet.approved_at.isoformat() if sheet.approved_at else None,
        "total_weightage": round(sum(goal.weightage for goal in sheet.goals), 2),
        "weighted_score": round(weighted_score, 2),
        "goals": goals,
    }


def ensure_seed_data(db: Session) -> None:
    if db.query(User).first():
        return

    admin = User(email="admin@atomberg.demo", name="Nisha HR", role=Role.admin.value, department="People Ops")
    manager = User(email="manager@atomberg.demo", name="Rohan Manager", role=Role.manager.value, department="Smart Appliances")
    manager2 = User(email="ops.manager@atomberg.demo", name="Isha Ops Manager", role=Role.manager.value, department="Operations")
    db.add_all([admin, manager, manager2])
    db.flush()
    employees = [
        User(email="employee@atomberg.demo", name="Aarav Employee", role=Role.employee.value, department="Smart Appliances", manager_id=manager.id),
        User(email="meera@atomberg.demo", name="Meera Engineer", role=Role.employee.value, department="Smart Appliances", manager_id=manager.id),
        User(email="kabir@atomberg.demo", name="Kabir Analyst", role=Role.employee.value, department="Operations", manager_id=manager2.id),
    ]
    cycle = Cycle(name="FY 2026 Goal Cycle", active_phase="goal_setting", active_quarter="Q1", window_open_month="May")
    db.add_all(employees + [cycle])
    db.commit()

    for employee in employees:
        sheet = sheet_for_employee(db, employee.id)
        sheet.status = SheetStatus.draft.value
        base_goals = [
            Goal(
                sheet_id=sheet.id,
                thrust_area="Customer Experience",
                title="Improve smart fan app satisfaction",
                description="Increase customer satisfaction score for IoT app connected devices.",
                uom_type=UomType.percent.value,
                direction=Direction.min.value,
                target_value=92,
                weightage=35,
                status=ProgressStatus.on_track.value,
            ),
            Goal(
                sheet_id=sheet.id,
                thrust_area="Operational Excellence",
                title="Reduce service turnaround time",
                description="Lower average service TAT for connected appliance tickets.",
                uom_type=UomType.numeric.value,
                direction=Direction.max.value,
                target_value=24,
                weightage=30,
                status=ProgressStatus.not_started.value,
            ),
            Goal(
                sheet_id=sheet.id,
                thrust_area="Innovation",
                title="Launch predictive maintenance pilot",
                description="Complete rollout plan and pilot launch for IoT anomaly alerts.",
                uom_type=UomType.timeline.value,
                direction=Direction.none.value,
                deadline=date(2026, 10, 15),
                weightage=20,
                status=ProgressStatus.not_started.value,
            ),
            Goal(
                sheet_id=sheet.id,
                thrust_area="Safety",
                title="Maintain zero critical safety incidents",
                description="Keep critical safety incidents at zero for the quarter.",
                uom_type=UomType.zero.value,
                direction=Direction.none.value,
                target_value=0,
                weightage=15,
                status=ProgressStatus.on_track.value,
            ),
        ]
        db.add_all(base_goals)
        db.flush()
        for goal in base_goals:
            db.add(
                Achievement(
                    goal_id=goal.id,
                    quarter="Q4",
                    actual_value=(goal.target_value or 0) * 0.85 if goal.target_value else None,
                    status=ProgressStatus.on_track.value,
                    comment="Prior quarter baseline",
                    updated_by_id=employee.id,
                )
            )
    kabir = db.query(User).filter(User.email == "kabir@atomberg.demo").first()
    if kabir:
        kabir_sheet = sheet_for_employee(db, kabir.id)
        kabir_sheet.status = SheetStatus.submitted.value
        kabir_sheet.submitted_at = datetime.utcnow() - timedelta(days=6)
    db.commit()
    run_escalation_scan(db)
    db.commit()


Base.metadata.create_all(bind=engine)
with SessionLocal() as seed_db:
    ensure_seed_data(seed_db)
    if seed_db.query(User).first() and not seed_db.query(EscalationLog).first():
        run_escalation_scan(seed_db)
        seed_db.commit()


app = FastAPI(title="AtomQuest GoalTrack API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/demo-users")
def demo_users(db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    return [
        {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "department": user.department}
        for user in db.query(User).order_by(User.role, User.name).all()
    ]


@app.get("/me")
def me(user: User = Depends(current_user)) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "department": user.department}


@app.get("/cycle")
def get_cycle(db: Session = Depends(db_session)) -> dict[str, Any]:
    cycle = active_cycle(db)
    return {"id": cycle.id, "name": cycle.name, "active_phase": cycle.active_phase, "active_quarter": cycle.active_quarter, "window_open_month": cycle.window_open_month}


@app.patch("/admin/cycle")
def update_cycle(
    payload: CyclePatch,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.admin)),
) -> dict[str, Any]:
    cycle = active_cycle(db)
    before = as_dict(cycle, ["active_phase", "active_quarter", "window_open_month"])
    cycle.active_phase = payload.active_phase
    cycle.active_quarter = payload.active_quarter
    cycle.window_open_month = payload.window_open_month
    audit(db, user, "cycle", cycle.id, "cycle_updated", before, as_dict(cycle, ["active_phase", "active_quarter", "window_open_month"]))
    db.commit()
    return get_cycle(db)


@app.get("/users")
def users(
    role: Optional[Role] = None,
    db: Session = Depends(db_session),
    _: User = Depends(current_user),
) -> list[dict[str, Any]]:
    query = db.query(User)
    if role:
        query = query.filter(User.role == role.value)
    return [
        {"id": item.id, "name": item.name, "email": item.email, "role": item.role, "department": item.department, "manager_id": item.manager_id}
        for item in query.order_by(User.name).all()
    ]


@app.get("/employee/sheet")
def employee_sheet(
    quarter: Optional[str] = Query(default=None),
    employee_id: Optional[int] = Query(default=None),
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.employee, Role.manager, Role.admin)),
) -> dict[str, Any]:
    target_employee_id = user.id if user.role == Role.employee.value else employee_id or user.id
    sheet = sheet_for_employee(db, target_employee_id)
    return serialize_sheet(sheet, quarter)


@app.get("/sheets/{sheet_id}")
def get_sheet(
    sheet_id: int,
    quarter: Optional[str] = None,
    db: Session = Depends(db_session),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    sheet = db.get(GoalSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Goal sheet not found")
    if user.role == Role.employee.value and sheet.employee_id != user.id:
        raise HTTPException(status_code=403, detail="Employees can only view their own sheet")
    if user.role == Role.manager.value and sheet.employee.manager_id != user.id:
        raise HTTPException(status_code=403, detail="Managers can only view their team")
    return serialize_sheet(sheet, quarter)


@app.put("/employee/goals")
def save_employee_goals(
    goals: list[GoalIn],
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.employee)),
) -> dict[str, Any]:
    validate_goal_payload(goals)
    sheet = sheet_for_employee(db, user.id)
    if sheet.locked:
        raise HTTPException(status_code=409, detail="Approved goals are locked. Ask Admin to unlock for exceptions.")
    if sheet.status == SheetStatus.submitted.value:
        raise HTTPException(status_code=409, detail="Submitted goals cannot be edited until returned by manager")

    existing_by_id = {goal.id: goal for goal in sheet.goals}
    incoming_ids = {goal.id for goal in goals if goal.id}
    for existing in list(sheet.goals):
        if existing.id not in incoming_ids:
            if existing.shared_group_id:
                raise HTTPException(status_code=409, detail="Shared goals cannot be deleted by recipients")
            db.delete(existing)

    for payload in goals:
        goal = existing_by_id.get(payload.id) if payload.id else Goal(sheet_id=sheet.id)
        before = as_dict(goal, ["title", "target_value", "deadline", "weightage"]) if payload.id else {}
        if goal.shared_group_id and not goal.is_primary_owner:
            goal.weightage = payload.weightage
        else:
            goal.thrust_area = payload.thrust_area
            goal.title = payload.title
            goal.description = payload.description
            goal.uom_type = payload.uom_type.value
            goal.direction = payload.direction.value
            goal.target_value = payload.target_value
            goal.deadline = payload.deadline
            goal.weightage = payload.weightage
        if not payload.id:
            db.add(goal)
        elif before != as_dict(goal, ["title", "target_value", "deadline", "weightage"]):
            audit(db, user, "goal", goal.id, "goal_draft_updated", before, as_dict(goal, ["title", "target_value", "deadline", "weightage"]))
    sheet.status = SheetStatus.draft.value
    sheet.returned_reason = None
    db.commit()
    db.refresh(sheet)
    return serialize_sheet(sheet)


@app.post("/employee/sheet/submit")
def submit_sheet(
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.employee)),
) -> dict[str, Any]:
    sheet = sheet_for_employee(db, user.id)
    if sheet.locked:
        raise HTTPException(status_code=409, detail="Approved goals are locked")
    validate_sheet(sheet)
    before = {"status": sheet.status}
    sheet.status = SheetStatus.submitted.value
    sheet.submitted_at = datetime.utcnow()
    sheet.returned_reason = None
    audit(db, user, "goal_sheet", sheet.id, "submitted_for_approval", before, {"status": sheet.status})
    db.refresh(sheet)
    notify_workflow_event(db, "goal_submitted", sheet, user)
    db.commit()
    return serialize_sheet(sheet)


@app.post("/employee/goals/{goal_id}/achievement")
def update_achievement(
    goal_id: int,
    payload: AchievementIn,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.employee)),
) -> dict[str, Any]:
    goal = db.get(Goal, goal_id)
    if not goal or goal.sheet.employee_id != user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    if goal.sheet.status != SheetStatus.approved.value:
        raise HTTPException(status_code=409, detail="Achievements can be updated only after manager approval")

    targets = [goal]
    if goal.shared_group_id and goal.is_primary_owner:
        targets = db.query(Goal).filter(Goal.shared_group_id == goal.shared_group_id).all()
    for target in targets:
        achievement = (
            db.query(Achievement)
            .filter(Achievement.goal_id == target.id, Achievement.quarter == payload.quarter)
            .first()
        )
        before = {}
        if not achievement:
            achievement = Achievement(goal_id=target.id, quarter=payload.quarter, updated_by_id=user.id)
            db.add(achievement)
        else:
            before = as_dict(achievement, ["actual_value", "completion_date", "status", "comment"])
        achievement.actual_value = payload.actual_value
        achievement.completion_date = payload.completion_date
        achievement.status = payload.status.value
        achievement.comment = payload.comment
        achievement.updated_by_id = user.id
        achievement.updated_at = datetime.utcnow()
        target.status = payload.status.value
        audit(db, user, "achievement", target.id, "achievement_updated", before, as_dict(achievement, ["actual_value", "completion_date", "status", "comment"]))
    db.commit()
    return serialize_sheet(goal.sheet, payload.quarter)


@app.get("/manager/team")
def manager_team(
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager)),
) -> list[dict[str, Any]]:
    employees = db.query(User).filter(User.manager_id == user.id).order_by(User.name).all()
    return [serialize_sheet(sheet_for_employee(db, employee.id), active_cycle(db).active_quarter) for employee in employees]


@app.get("/manager/approvals")
def approvals(
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager)),
) -> list[dict[str, Any]]:
    sheets = (
        db.query(GoalSheet)
        .join(User, GoalSheet.employee_id == User.id)
        .filter(User.manager_id == user.id, GoalSheet.status == SheetStatus.submitted.value)
        .all()
    )
    return [serialize_sheet(sheet) for sheet in sheets]


@app.patch("/manager/goals/{goal_id}")
def manager_patch_goal(
    goal_id: int,
    payload: ManagerGoalPatch,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager)),
) -> dict[str, Any]:
    goal = db.get(Goal, goal_id)
    if not goal or goal.sheet.employee.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    if goal.sheet.status != SheetStatus.submitted.value:
        raise HTTPException(status_code=409, detail="Manager inline edits are allowed only during approval")
    before = as_dict(goal, ["target_value", "deadline", "weightage"])
    if payload.target_value is not None:
        goal.target_value = payload.target_value
    if payload.deadline is not None:
        goal.deadline = payload.deadline
    if payload.weightage is not None:
        goal.weightage = payload.weightage
    audit(db, user, "goal", goal.id, "manager_inline_edit", before, as_dict(goal, ["target_value", "deadline", "weightage"]))
    db.commit()
    return serialize_sheet(goal.sheet)


@app.post("/manager/sheets/{sheet_id}/approve")
def approve_sheet(
    sheet_id: int,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager)),
) -> dict[str, Any]:
    sheet = db.get(GoalSheet, sheet_id)
    if not sheet or sheet.employee.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Goal sheet not found")
    validate_sheet(sheet)
    before = {"status": sheet.status, "locked": sheet.locked}
    sheet.status = SheetStatus.approved.value
    sheet.locked = True
    sheet.approved_at = datetime.utcnow()
    audit(db, user, "goal_sheet", sheet.id, "manager_approved", before, {"status": sheet.status, "locked": sheet.locked})
    db.refresh(sheet)
    notify_workflow_event(db, "goal_approved", sheet, user)
    db.commit()
    return serialize_sheet(sheet)


@app.post("/manager/sheets/{sheet_id}/return")
def return_sheet(
    sheet_id: int,
    payload: ReturnIn,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager)),
) -> dict[str, Any]:
    sheet = db.get(GoalSheet, sheet_id)
    if not sheet or sheet.employee.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Goal sheet not found")
    before = {"status": sheet.status}
    sheet.status = SheetStatus.returned.value
    sheet.returned_reason = payload.reason
    audit(db, user, "goal_sheet", sheet.id, "returned_for_rework", before, {"status": sheet.status, "reason": payload.reason})
    db.refresh(sheet)
    notify_workflow_event(db, "goal_returned", sheet, user)
    db.commit()
    return serialize_sheet(sheet)


@app.post("/manager/shared-goals")
def create_shared_goal(
    payload: SharedGoalIn,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager, Role.admin)),
) -> dict[str, Any]:
    recipients = set(payload.recipient_employee_ids + [payload.primary_owner_id])
    group = SharedGoalGroup(
        title=payload.title,
        description=payload.description,
        thrust_area=payload.thrust_area,
        uom_type=payload.uom_type.value,
        direction=payload.direction.value,
        target_value=payload.target_value,
        deadline=payload.deadline,
        primary_owner_id=payload.primary_owner_id,
        created_by_id=user.id,
    )
    db.add(group)
    db.flush()
    for employee_id in recipients:
        employee = db.get(User, employee_id)
        if not employee or employee.role != Role.employee.value:
            continue
        if user.role == Role.manager.value and employee.manager_id != user.id:
            continue
        sheet = sheet_for_employee(db, employee.id)
        if sheet.locked:
            continue
        db.add(
            Goal(
                sheet_id=sheet.id,
                thrust_area=payload.thrust_area,
                title=payload.title,
                description=payload.description,
                uom_type=payload.uom_type.value,
                direction=payload.direction.value,
                target_value=payload.target_value,
                deadline=payload.deadline,
                weightage=payload.weightage,
                shared_group_id=group.id,
                is_primary_owner=employee.id == payload.primary_owner_id,
            )
        )
    audit(db, user, "shared_goal_group", group.id, "shared_goal_pushed", {}, payload.model_dump())
    db.commit()
    return {"id": group.id, "message": "Shared goal pushed to unlocked recipient sheets"}


@app.post("/manager/sheets/{sheet_id}/checkins")
def save_checkin(
    sheet_id: int,
    payload: CheckInIn,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.manager)),
) -> dict[str, Any]:
    sheet = db.get(GoalSheet, sheet_id)
    if not sheet or sheet.employee.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Goal sheet not found")
    checkin = db.query(CheckIn).filter(CheckIn.sheet_id == sheet_id, CheckIn.quarter == payload.quarter).first()
    before = {}
    if not checkin:
        checkin = CheckIn(sheet_id=sheet_id, quarter=payload.quarter, manager_id=user.id, comment=payload.comment)
        db.add(checkin)
    else:
        before = {"comment": checkin.comment}
        checkin.comment = payload.comment
        checkin.completed_at = datetime.utcnow()
    audit(db, user, "checkin", sheet_id, "manager_checkin_completed", before, {"quarter": payload.quarter, "comment": payload.comment})
    db.refresh(sheet)
    notify_workflow_event(db, "checkin_completed", sheet, user)
    db.commit()
    return serialize_sheet(sheet, payload.quarter)


@app.post("/admin/sheets/{sheet_id}/unlock")
def unlock_sheet(
    sheet_id: int,
    payload: UnlockIn,
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.admin)),
) -> dict[str, Any]:
    sheet = db.get(GoalSheet, sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Goal sheet not found")
    before = {"status": sheet.status, "locked": sheet.locked}
    sheet.locked = False
    sheet.status = SheetStatus.returned.value
    sheet.returned_reason = f"Admin unlocked: {payload.reason}"
    audit(db, user, "goal_sheet", sheet.id, "admin_unlocked_after_lock", before, {"status": sheet.status, "locked": sheet.locked, "reason": payload.reason})
    db.commit()
    return serialize_sheet(sheet)


@app.get("/admin/audit")
def audit_logs(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin)),
) -> list[dict[str, Any]]:
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": row.id,
            "actor": row.actor.name,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "action": row.action,
            "before": json.loads(row.before_json),
            "after": json.loads(row.after_json),
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/admin/sheets")
def admin_sheets(
    quarter: Optional[str] = None,
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin)),
) -> list[dict[str, Any]]:
    return [serialize_sheet(sheet, quarter) for sheet in db.query(GoalSheet).join(User, GoalSheet.employee_id == User.id).order_by(User.department, User.name).all()]


@app.get("/analytics/summary")
def analytics_summary(
    db: Session = Depends(db_session),
    _: User = Depends(current_user),
) -> dict[str, Any]:
    sheets = db.query(GoalSheet).all()
    goals = db.query(Goal).all()
    checkins = db.query(CheckIn).all()
    active_q = active_cycle(db).active_quarter
    employees = db.query(User).filter(User.role == Role.employee.value).all()
    managers = db.query(User).filter(User.role == Role.manager.value).all()

    status_counts: dict[str, int] = {}
    thrust_counts: dict[str, int] = {}
    for goal in goals:
        status_counts[goal.status] = status_counts.get(goal.status, 0) + 1
        thrust_counts[goal.thrust_area] = thrust_counts.get(goal.thrust_area, 0) + 1

    manager_completion = []
    for manager in managers:
        team = [employee for employee in employees if employee.manager_id == manager.id]
        team_sheet_ids = [sheet_for_employee(db, employee.id).id for employee in team]
        completed = len([item for item in checkins if item.sheet_id in team_sheet_ids and item.quarter == active_q])
        manager_completion.append({"manager": manager.name, "team_size": len(team), "completed_checkins": completed})

    return {
        "employees": len(employees),
        "approved_sheets": len([sheet for sheet in sheets if sheet.status == SheetStatus.approved.value]),
        "submitted_sheets": len([sheet for sheet in sheets if sheet.status == SheetStatus.submitted.value]),
        "draft_or_returned_sheets": len([sheet for sheet in sheets if sheet.status in {SheetStatus.draft.value, SheetStatus.returned.value}]),
        "active_quarter": active_q,
        "checkins_completed": len([item for item in checkins if item.quarter == active_q]),
        "goal_status_distribution": [{"name": key, "value": value} for key, value in status_counts.items()],
        "thrust_area_distribution": [{"name": key, "value": value} for key, value in thrust_counts.items()],
        "manager_completion": manager_completion,
        **advanced_analytics(db),
    }


@app.get("/auth/entra/status")
def entra_status() -> dict[str, Any]:
    return {
        "enabled": os.getenv("ENTRA_ENABLED", "demo").lower() != "false",
        "tenant": os.getenv("ENTRA_TENANT_ID", "atomberg-demo.onmicrosoft.com"),
        "sso_protocol": "OpenID Connect / OAuth2",
        "group_role_mapping": ENTRA_GROUP_ROLE_MAP,
        "note": "Demo mode simulates Entra SSO; production uses Microsoft Graph for hierarchy sync.",
    }


@app.post("/auth/entra/sso")
def entra_sso(payload: EntraSsoIn, db: Session = Depends(db_session)) -> dict[str, Any]:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not provisioned from Entra ID")
    groups = entra_groups_for_user(user)
    mapped_role = ENTRA_GROUP_ROLE_MAP.get(next((group for group in groups if group in ENTRA_GROUP_ROLE_MAP), ""), user.role)
    manager = user.manager
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "department": user.department},
        "entra": {
            "oid": f"demo-{user.id}",
            "groups": groups,
            "mapped_role": mapped_role,
            "manager_email": manager.email if manager else None,
            "deep_link": portal_deep_link(user.email),
        },
    }


@app.get("/org/hierarchy")
def org_hierarchy(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin, Role.manager)),
) -> dict[str, Any]:
    return {"source": "Microsoft Entra ID (demo sync)", "roots": build_org_hierarchy(db)}


@app.get("/admin/notifications")
def list_notifications(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin)),
) -> list[dict[str, Any]]:
    rows = db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(50).all()
    return [
        {
            "id": row.id,
            "channel": row.channel,
            "event_type": row.event_type,
            "recipient_email": row.recipient_email,
            "subject": row.subject,
            "body": row.body,
            "deep_link": row.deep_link,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/admin/escalations")
def list_escalations(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin)),
) -> list[dict[str, Any]]:
    rows = db.query(EscalationLog).order_by(EscalationLog.created_at.desc()).limit(50).all()
    return [
        {
            "id": row.id,
            "rule_code": row.rule_code,
            "severity": row.severity,
            "subject_user": row.subject_user.name,
            "escalated_to_role": row.escalated_to_role,
            "message": row.message,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.post("/admin/escalations/run")
def trigger_escalations(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin)),
) -> dict[str, Any]:
    created = run_escalation_scan(db)
    db.commit()
    return {"created": len(created), "message": "Escalation scan completed"}


@app.get("/analytics/advanced")
def analytics_advanced(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin, Role.manager)),
) -> dict[str, Any]:
    return advanced_analytics(db)


@app.get("/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(db_session),
    user: User = Depends(require_role(Role.admin)),
) -> dict[str, Any]:
    return analytics_summary(db, user)


@app.get("/reports/achievements.csv")
def achievement_report(
    db: Session = Depends(db_session),
    _: User = Depends(require_role(Role.admin, Role.manager)),
) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "employee",
        "department",
        "manager",
        "goal_title",
        "thrust_area",
        "uom_type",
        "target",
        "deadline",
        "weightage",
        "quarter",
        "actual",
        "completion_date",
        "status",
        "progress_score",
    ])
    for goal in db.query(Goal).join(GoalSheet).join(User, GoalSheet.employee_id == User.id).all():
        if goal.achievements:
            for achievement in goal.achievements:
                writer.writerow([
                    goal.sheet.employee.name,
                    goal.sheet.employee.department,
                    goal.sheet.employee.manager.name if goal.sheet.employee.manager else "",
                    goal.title,
                    goal.thrust_area,
                    goal.uom_type,
                    goal.target_value,
                    goal.deadline,
                    goal.weightage,
                    achievement.quarter,
                    achievement.actual_value,
                    achievement.completion_date,
                    achievement.status,
                    progress_score(goal, achievement),
                ])
        else:
            writer.writerow([
                goal.sheet.employee.name,
                goal.sheet.employee.department,
                goal.sheet.employee.manager.name if goal.sheet.employee.manager else "",
                goal.title,
                goal.thrust_area,
                goal.uom_type,
                goal.target_value,
                goal.deadline,
                goal.weightage,
                "",
                "",
                "",
                goal.status,
                0,
            ])
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=atomquest-achievement-report.csv"},
    )
