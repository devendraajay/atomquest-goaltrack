import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";

const configuredApiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_URL = configuredApiUrl.startsWith("http") ? configuredApiUrl : `https://${configuredApiUrl}`;
const COLORS = ["#6366f1", "#14b8a6", "#f97316", "#8b5cf6", "#10b981", "#ef4444"];

type Role = "employee" | "manager" | "admin";

type DemoUser = {
  id: number;
  name: string;
  email: string;
  role: Role;
  department: string;
};

type Goal = {
  id?: number;
  thrust_area: string;
  title: string;
  description: string;
  uom_type: "numeric" | "percent" | "timeline" | "zero";
  direction: "min" | "max" | "none";
  target_value?: number | null;
  deadline?: string | null;
  weightage: number;
  status?: string;
  read_only_shared_fields?: boolean;
  achievement?: {
    quarter: string;
    actual_value?: number | null;
    completion_date?: string | null;
    status: string;
    comment?: string;
    progress_score: number;
  } | null;
};

type Sheet = {
  id: number;
  employee: DemoUser;
  status: string;
  locked: boolean;
  returned_reason?: string | null;
  total_weightage: number;
  weighted_score: number;
  goals: Goal[];
};

type Analytics = {
  employees: number;
  approved_sheets: number;
  submitted_sheets: number;
  draft_or_returned_sheets: number;
  active_quarter: string;
  checkins_completed: number;
  goal_status_distribution: Array<{ name: string; value: number }>;
  thrust_area_distribution: Array<{ name: string; value: number }>;
  manager_completion: Array<{ manager: string; team_size: number; completed_checkins: number }>;
};

type ApiClient = {
  request<T>(path: string, options?: RequestInit): Promise<T>;
};

const blankGoal = (): Goal => ({
  thrust_area: "Customer Experience",
  title: "",
  description: "",
  uom_type: "numeric",
  direction: "min",
  target_value: 100,
  deadline: null,
  weightage: 10,
});

function App() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [currentEmail, setCurrentEmail] = useState("employee@atomberg.demo");
  const [message, setMessage] = useState("");
  const currentUser = users.find((user) => user.email === currentEmail);

  const api: ApiClient = useMemo(
    () => ({
      async request<T>(path: string, options: RequestInit = {}): Promise<T> {
        const response = await fetch(`${API_URL}${path}`, {
          ...options,
          headers: {
            "Content-Type": "application/json",
            "X-User-Email": currentEmail,
            ...(options.headers || {}),
          },
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(body.detail || "Request failed");
        }
        return response.json();
      },
    }),
    [currentEmail],
  );

  useEffect(() => {
    fetch(`${API_URL}/auth/demo-users`)
      .then((response) => response.json())
      .then(setUsers)
      .catch((error) => setMessage(error.message));
  }, []);

  const flash = (text: string) => {
    setMessage(text);
    window.setTimeout(() => setMessage(""), 3500);
  };

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-inner">
          <div className="brand-block">
            <div className="brand-mark">
              <span className="brand-icon" aria-hidden="true">◎</span>
              <p className="eyebrow">AtomQuest Hackathon 2026</p>
            </div>
            <h1>GoalTrack Portal</h1>
            <p className="tagline">
              Digital goal setting, L1 approval, quarterly check-ins, audit trail, and HR analytics in one portal.
            </p>
            <div className="feature-pills">
              <span className="feature-pill">◎ Goal sheets</span>
              <span className="feature-pill">✓ L1 approvals</span>
              <span className="feature-pill">◐ Quarterly tracking</span>
              <span className="feature-pill">▣ HR analytics</span>
            </div>
          </div>
          <div className="user-card">
            <span className="user-card-label">Switch demo persona</span>
          <select value={currentEmail} onChange={(event) => setCurrentEmail(event.target.value)}>
              {users.length === 0 && <option value={currentEmail}>Loading users...</option>}
              {users.map((user) => (
                <option key={user.email} value={user.email}>
                  {user.name} · {user.role}
                </option>
              ))}
            </select>
            {currentUser && (
              <div className="user-meta">
                <span className={`role-pill ${currentUser.role}`}>{currentUser.role}</span>
                <span className="dept-tag">{currentUser.department}</span>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="app-main">
        {!users.length && !message && (
          <section className="panel">
            <LoadingState label="Connecting to GoalTrack API..." />
          </section>
        )}
        {currentUser?.role === "employee" && <EmployeePortal api={api} flash={flash} />}
        {currentUser?.role === "manager" && <ManagerPortal api={api} flash={flash} />}
        {currentUser?.role === "admin" && <AdminPortal api={api} flash={flash} users={users} />}
      </main>

      {message && <div className="toast">{message}</div>}

      <footer className="site-footer">AtomQuest GoalTrack · Built for AtomQuest Hackathon 2026</footer>
    </div>
  );
}

function EmployeePortal({ api, flash }: { api: ApiClient; flash: (text: string) => void }) {
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [quarter, setQuarter] = useState("Q1");

  const load = () =>
    api
      .request<Sheet>(`/employee/sheet?quarter=${quarter}`)
      .then((data) => {
        setSheet(data);
        setGoals(data.goals.length ? data.goals : [blankGoal()]);
      })
      .catch((error: Error) => flash(error.message));

  useEffect(() => {
    void load();
  }, [quarter]);

  const updateGoal = (index: number, patch: Partial<Goal>) => {
    setGoals((items) => items.map((goal, itemIndex) => (itemIndex === index ? { ...goal, ...patch } : goal)));
  };

  const saveGoals = async () => {
    const payload = goals.map((goal) => ({ ...goal, target_value: goal.target_value ? Number(goal.target_value) : null, weightage: Number(goal.weightage) }));
    const updated = await api.request<Sheet>("/employee/goals", { method: "PUT", body: JSON.stringify(payload) });
    setSheet(updated);
    setGoals(updated.goals);
    flash("Goal sheet saved.");
  };

  const submit = async () => {
    const updated = await api.request<Sheet>("/employee/sheet/submit", { method: "POST", body: "{}" });
    setSheet(updated);
    flash("Submitted to manager for approval.");
  };

  const updateAchievement = async (goal: Goal, actual: string, status: string, completionDate: string) => {
    const updated = await api.request<Sheet>(`/employee/goals/${goal.id}/achievement`, {
      method: "POST",
      body: JSON.stringify({
        quarter,
        actual_value: actual ? Number(actual) : null,
        completion_date: completionDate || null,
        status,
        comment: `Updated during ${quarter} check-in`,
      }),
    });
    setSheet(updated);
    setGoals(updated.goals);
    flash("Achievement updated.");
  };

  if (!sheet) {
    return (
      <section className="panel">
        <LoadingState label="Loading employee workspace..." />
      </section>
    );
  }

  const weightClass =
    sheet.total_weightage === 100 ? "complete" : sheet.total_weightage > 100 ? "over" : "";

  return (
    <section className="grid two content-section">
      <div className="panel panel-accent-teal">
        <div className="panel-header-row">
          <PanelTitle icon="🎯" iconTone="teal" title="Employee Goal Sheet" subtitle="Draft, submit, and track your annual objectives" />
          <StatusBadge status={sheet.status} />
        </div>
        <div className="weight-bar" title="Total weightage must equal 100%">
          <div className={`weight-bar-fill ${weightClass}`} style={{ width: `${Math.min(sheet.total_weightage, 100)}%` }} />
        </div>
        <div className="weight-label">
          <span className="hint">Total weightage</span>
          <strong>
            {sheet.total_weightage}%
            {sheet.total_weightage !== 100 && " · need 100% to submit"}
          </strong>
        </div>
        {sheet.returned_reason && <div className="warning">{sheet.returned_reason}</div>}
        {goals.map((goal, index) => (
          <div className="goal-card" key={goal.id || index}>
            <span className="goal-index">{index + 1}</span>
            <div className="row">
              <input disabled={sheet.locked || goal.read_only_shared_fields} value={goal.title} placeholder="Goal title" onChange={(event) => updateGoal(index, { title: event.target.value })} />
              <input type="number" value={goal.weightage} onChange={(event) => updateGoal(index, { weightage: Number(event.target.value) })} />
            </div>
            <textarea disabled={sheet.locked || goal.read_only_shared_fields} value={goal.description} placeholder="Description" onChange={(event) => updateGoal(index, { description: event.target.value })} />
            <div className="row">
              <select disabled={sheet.locked || goal.read_only_shared_fields} value={goal.thrust_area} onChange={(event) => updateGoal(index, { thrust_area: event.target.value })}>
                <option>Customer Experience</option>
                <option>Operational Excellence</option>
                <option>Innovation</option>
                <option>Safety</option>
                <option>People</option>
              </select>
              <select disabled={sheet.locked || goal.read_only_shared_fields} value={goal.uom_type} onChange={(event) => updateGoal(index, { uom_type: event.target.value as Goal["uom_type"] })}>
                <option value="numeric">Numeric</option>
                <option value="percent">%</option>
                <option value="timeline">Timeline</option>
                <option value="zero">Zero-based</option>
              </select>
              <select disabled={sheet.locked || goal.read_only_shared_fields} value={goal.direction} onChange={(event) => updateGoal(index, { direction: event.target.value as Goal["direction"] })}>
                <option value="min">Higher is better</option>
                <option value="max">Lower is better</option>
                <option value="none">Not applicable</option>
              </select>
            </div>
            <div className="row">
              <input disabled={sheet.locked || goal.read_only_shared_fields} type="number" value={goal.target_value ?? ""} placeholder="Target" onChange={(event) => updateGoal(index, { target_value: event.target.value ? Number(event.target.value) : null })} />
              <input disabled={sheet.locked || goal.read_only_shared_fields} type="date" value={goal.deadline || ""} onChange={(event) => updateGoal(index, { deadline: event.target.value })} />
            </div>
            {goal.read_only_shared_fields && <small>Shared KPI: only weightage is editable for recipients.</small>}
          </div>
        ))}
        <div className="actions">
          <button className="ghost" disabled={sheet.locked || goals.length >= 8} onClick={() => setGoals([...goals, blankGoal()])}>
            + Add Goal
          </button>
          <button className="secondary" disabled={sheet.locked} onClick={saveGoals}>
            Save Draft
          </button>
          <button disabled={sheet.locked || sheet.total_weightage !== 100} onClick={submit}>
            Submit for Approval
          </button>
        </div>
      </div>

      <div className="panel panel-accent-purple">
        <PanelTitle icon="📊" iconTone="purple" title="Quarterly Achievement" subtitle="Actuals are accepted after L1 approval" />
        <QuarterTabs value={quarter} onChange={setQuarter} />
        {sheet.goals.map((goal) => (
          <AchievementForm key={goal.id} goal={goal} disabled={sheet.status !== "approved"} onSave={updateAchievement} />
        ))}
      </div>
    </section>
  );
}

function AchievementForm({ goal, disabled, onSave }: { goal: Goal; disabled: boolean; onSave: (goal: Goal, actual: string, status: string, completionDate: string) => void }) {
  const [actual, setActual] = useState(goal.achievement?.actual_value?.toString() || "");
  const [status, setStatus] = useState(goal.achievement?.status || "On Track");
  const [completionDate, setCompletionDate] = useState(goal.achievement?.completion_date || "");
  return (
    <div className="goal-card compact">
      <strong>{goal.title}</strong>
      <span>Target: {goal.target_value || goal.deadline || "Zero"} | Score: {goal.achievement?.progress_score || 0}%</span>
      <div className="row">
        <input disabled={disabled} placeholder="Actual" value={actual} onChange={(event) => setActual(event.target.value)} />
        <input disabled={disabled} type="date" value={completionDate} onChange={(event) => setCompletionDate(event.target.value)} />
        <select disabled={disabled} value={status} onChange={(event) => setStatus(event.target.value)}>
          <option>Not Started</option>
          <option>On Track</option>
          <option>Completed</option>
        </select>
        <button disabled={disabled} onClick={() => onSave(goal, actual, status, completionDate)}>Save</button>
      </div>
    </div>
  );
}

function ManagerPortal({ api, flash }: { api: ApiClient; flash: (text: string) => void }) {
  const [team, setTeam] = useState<Sheet[]>([]);
  const [approvals, setApprovals] = useState<Sheet[]>([]);
  const [employees, setEmployees] = useState<DemoUser[]>([]);
  const [selected, setSelected] = useState<Sheet | null>(null);
  const [comment, setComment] = useState("Discussed progress, blockers, and next-quarter support actions.");
  const [sharedGoal, setSharedGoal] = useState({
    title: "Reduce IoT device repeat complaints",
    description: "Department KPI shared across the Smart Appliances team.",
    thrust_area: "Customer Experience",
    uom_type: "percent",
    direction: "min",
    target_value: 95,
    weightage: 10,
  });

  const load = () => {
    api.request<Sheet[]>("/manager/team").then(setTeam).catch((error: Error) => flash(error.message));
    api.request<Sheet[]>("/manager/approvals").then(setApprovals).catch((error: Error) => flash(error.message));
    api.request<DemoUser[]>("/users?role=employee").then(setEmployees).catch((error: Error) => flash(error.message));
  };
  useEffect(load, []);

  const approve = async (sheet: Sheet) => {
    await api.request(`/manager/sheets/${sheet.id}/approve`, { method: "POST", body: "{}" });
    flash("Goal sheet approved and locked.");
    load();
  };

  const returnSheet = async (sheet: Sheet) => {
    await api.request(`/manager/sheets/${sheet.id}/return`, { method: "POST", body: JSON.stringify({ reason: "Please rebalance weightage and clarify measurable targets." }) });
    flash("Returned for rework.");
    load();
  };

  const checkIn = async (sheet: Sheet) => {
    await api.request(`/manager/sheets/${sheet.id}/checkins`, { method: "POST", body: JSON.stringify({ quarter: "Q1", comment }) });
    flash("Manager check-in saved.");
    load();
  };

  const pushSharedGoal = async () => {
    const teamEmployeeIds = team.map((sheet) => sheet.employee.id);
    await api.request("/manager/shared-goals", {
      method: "POST",
      body: JSON.stringify({
        ...sharedGoal,
        primary_owner_id: teamEmployeeIds[0],
        recipient_employee_ids: teamEmployeeIds,
      }),
    });
    flash("Shared departmental KPI pushed to unlocked team sheets.");
    load();
  };

  return (
    <section className="grid two content-section">
      <div className="panel panel-accent-orange">
        <PanelTitle icon="✅" iconTone="orange" title="L1 Approval Queue" subtitle={`${approvals.length} submitted sheets awaiting action`} />
        {approvals.map((sheet) => (
          <div className="goal-card approval-sheet-card" key={sheet.id}>
            <div className="panel-header-row">
              <strong>{sheet.employee.name}</strong>
              <StatusBadge status={sheet.status} />
            </div>
            <span>{sheet.total_weightage}% weightage · {sheet.goals.length} goals</span>
            {sheet.goals.map((goal) => (
              <ApprovalGoalEditor key={goal.id} api={api} goal={goal} onSaved={load} />
            ))}
            <div className="actions">
              <button onClick={() => approve(sheet)}>Approve and Lock</button>
              <button className="secondary" onClick={() => returnSheet(sheet)}>Return</button>
            </div>
          </div>
        ))}
        {!approvals.length && <EmptyState icon="📭" text="No pending approvals. Use employee role to submit a sheet." />}
      </div>

      <div className="panel panel-accent-teal">
        <PanelTitle icon="👥" iconTone="teal" title="Team Check-ins" subtitle="Planned vs actual progress for direct reports" />
        <div className="cards">
          {team.map((sheet) => (
            <button
              className={`team-card${selected?.id === sheet.id ? " selected" : ""}`}
              key={sheet.id}
              onClick={() => setSelected(sheet)}
            >
              <div className="team-card-header">
                <Avatar name={sheet.employee.name} />
                <div>
                  <strong>{sheet.employee.name}</strong>
                  <span>{sheet.status}</span>
                </div>
              </div>
              <span className="score-ring">{sheet.weighted_score}%</span>
            </button>
          ))}
        </div>
        {selected && (
          <div className="drawer">
            <h3>{selected.employee.name}</h3>
            {selected.goals.map((goal) => (
              <div className="mini-row" key={goal.id}>
                <span>{goal.title}</span>
                <b>{goal.achievement?.progress_score || 0}%</b>
              </div>
            ))}
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
            <button onClick={() => checkIn(selected)}>Complete Q1 Check-in</button>
          </div>
        )}
      </div>

      <div className="panel wide panel-accent-purple">
        <PanelTitle icon="🔗" iconTone="purple" title="Shared Department KPI" subtitle="Push one manager-owned KPI to all unlocked team goal sheets" />
        <div className="row">
          <input value={sharedGoal.title} onChange={(event) => setSharedGoal({ ...sharedGoal, title: event.target.value })} />
          <input type="number" value={sharedGoal.target_value} onChange={(event) => setSharedGoal({ ...sharedGoal, target_value: Number(event.target.value) })} />
          <input type="number" value={sharedGoal.weightage} onChange={(event) => setSharedGoal({ ...sharedGoal, weightage: Number(event.target.value) })} />
          <button disabled={!team.length || !employees.length} onClick={pushSharedGoal}>Push Shared Goal</button>
        </div>
      </div>
    </section>
  );
}

function ApprovalGoalEditor({ api, goal, onSaved }: { api: ApiClient; goal: Goal; onSaved: () => void }) {
  const [target, setTarget] = useState(goal.target_value?.toString() || "");
  const [deadline, setDeadline] = useState(goal.deadline || "");
  const [weightage, setWeightage] = useState(goal.weightage.toString());

  const save = async () => {
    await api.request(`/manager/goals/${goal.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        target_value: target ? Number(target) : null,
        deadline: deadline || null,
        weightage: Number(weightage),
      }),
    });
    onSaved();
  };

  return (
    <div className="approval-editor">
      <span className="approval-editor-title">{goal.title}</span>
      <div className="approval-editor-fields">
        <div className="approval-field">
          <label htmlFor={`target-${goal.id}`}>Target</label>
          <input id={`target-${goal.id}`} value={target} onChange={(event) => setTarget(event.target.value)} placeholder="Target" />
        </div>
        <div className="approval-field">
          <label htmlFor={`deadline-${goal.id}`}>Deadline</label>
          <input id={`deadline-${goal.id}`} type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} />
        </div>
        <div className="approval-field">
          <label htmlFor={`weight-${goal.id}`}>Weight %</label>
          <input id={`weight-${goal.id}`} type="number" value={weightage} onChange={(event) => setWeightage(event.target.value)} />
        </div>
      </div>
      <div className="approval-editor-actions">
        <button type="button" className="secondary" onClick={save}>
          Save edit
        </button>
      </div>
    </div>
  );
}

function AdminPortal({ api, flash, users }: { api: ApiClient; flash: (text: string) => void; users: DemoUser[] }) {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [audit, setAudit] = useState<any[]>([]);
  const [sheets, setSheets] = useState<Sheet[]>([]);

  const load = () => {
    api.request<Analytics>("/admin/dashboard").then(setAnalytics).catch((error: Error) => flash(error.message));
    api.request<any[]>("/admin/audit").then(setAudit).catch((error: Error) => flash(error.message));
    api.request<Sheet[]>("/admin/sheets?quarter=Q1").then(setSheets).catch((error: Error) => flash(error.message));
  };
  useEffect(load, []);

  const downloadCsv = () => {
    window.open(`${API_URL}/reports/achievements.csv`, "_blank");
  };

  const unlockSheet = async (sheet: Sheet) => {
    await api.request(`/admin/sheets/${sheet.id}/unlock`, {
      method: "POST",
      body: JSON.stringify({ reason: "Approved exception for hackathon demo" }),
    });
    flash(`${sheet.employee.name}'s sheet unlocked with audit log.`);
    load();
  };

  if (!analytics) {
    return (
      <section className="panel">
        <LoadingState label="Loading admin dashboard..." />
      </section>
    );
  }

  return (
    <section className="grid two content-section">
      <div className="panel">
        <PanelTitle icon="📈" iconTone="indigo" title="HR Completion Dashboard" subtitle={`Active quarter: ${analytics.active_quarter}`} />
        <div className="metrics">
          <Metric icon="👤" variant="m1" label="Employees" value={analytics.employees} />
          <Metric icon="✓" variant="m2" label="Approved" value={analytics.approved_sheets} />
          <Metric icon="↑" variant="m3" label="Submitted" value={analytics.submitted_sheets} />
          <Metric icon="💬" variant="m4" label="Check-ins" value={analytics.checkins_completed} />
        </div>
        <div className="chart-wrap">
          <p className="hint" style={{ marginBottom: 8 }}>Goal status distribution</p>
          <div className="chart">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={analytics.goal_status_distribution} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={3}>
                  {analytics.goal_status_distribution.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} stroke="none" />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <button className="accent" onClick={downloadCsv}>
          ↓ Download Achievement CSV
        </button>
      </div>

      <div className="panel panel-accent-teal">
        <PanelTitle icon="📊" iconTone="teal" title="Analytics Module" subtitle="Goal distribution and manager effectiveness" />
        <div className="chart-wrap">
          <p className="hint" style={{ marginBottom: 8 }}>Goals by thrust area</p>
          <div className="chart">
            <ResponsiveContainer>
            <BarChart data={analytics.thrust_area_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="name" hide />
              <YAxis tick={{ fill: "#64748b", fontSize: 12 }} />
              <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0" }} />
              <Bar dataKey="value" fill="url(#barGradient)" radius={[8, 8, 0, 0]} />
              <defs>
                <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" />
                  <stop offset="100%" stopColor="#14b8a6" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
          </div>
        </div>
        {analytics.manager_completion.map((item) => (
          <div className="mini-row" key={item.manager}>
            <span>{item.manager}</span>
            <b>{item.completed_checkins}/{item.team_size} check-ins</b>
          </div>
        ))}
      </div>

      <div className="panel wide panel-accent-orange">
        <PanelTitle icon="🔓" iconTone="orange" title="Exception Handling" subtitle="Admin can unlock approved goal sheets and preserve auditability" />
        {sheets.map((sheet) => (
          <div className="mini-row" key={sheet.id}>
            <span>{sheet.employee.name} - {sheet.status} - {sheet.total_weightage}%</span>
            <button disabled={!sheet.locked} onClick={() => unlockSheet(sheet)}>Unlock</button>
          </div>
        ))}
      </div>

      <div className="panel wide panel-accent-purple">
        <PanelTitle icon="📋" iconTone="purple" title="Audit Trail" subtitle="All locked-goal exceptions and workflow changes are tracked" />
        <div className="audit-table">
          <div className="audit-table-header">
            <span>Timestamp</span>
            <span>Actor</span>
            <span>Action</span>
            <span>Entity</span>
          </div>
          {audit.map((row) => (
            <div className="audit-row" key={row.id}>
              <span>{new Date(row.created_at).toLocaleString()}</span>
              <strong>{row.actor}</strong>
              <span>{row.action}</span>
              <code>{row.entity_type} #{row.entity_id}</code>
            </div>
          ))}
        </div>
        <p className="hint">Demo credentials: {users.map((user) => `${user.role}: ${user.email}`).join(" | ")}</p>
      </div>
    </section>
  );
}

function PanelTitle({
  title,
  subtitle,
  icon,
  iconTone = "indigo",
}: {
  title: string;
  subtitle: string;
  icon?: string;
  iconTone?: "indigo" | "teal" | "orange" | "purple";
}) {
  return (
    <div className="panel-title">
      {icon && <span className={`panel-icon ${iconTone}`}>{icon}</span>}
      <div className="panel-title-text">
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  icon,
  variant = "m1",
}: {
  label: string;
  value: number;
  icon?: string;
  variant?: "m1" | "m2" | "m3" | "m4";
}) {
  return (
    <div className={`metric ${variant}`}>
      {icon && <span className="metric-icon">{icon}</span>}
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function EmptyState({ text, icon = "📋" }: { text: string; icon?: string }) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon}</span>
      {text}
    </div>
  );
}

function QuarterTabs({ value, onChange }: { value: string; onChange: (q: string) => void }) {
  return (
    <div className="quarter-tabs">
      {["Q1", "Q2", "Q3", "Q4"].map((item) => (
        <button key={item} type="button" className={`quarter-tab${value === item ? " active" : ""}`} onClick={() => onChange(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return <span className="avatar">{initials}</span>;
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-panel">
      <div className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase().replace(/\s+/g, "_");
  const variant = ["draft", "submitted", "approved", "returned"].includes(normalized)
    ? normalized
    : "draft";
  return <span className={`status-badge ${variant}`}>{status.replace(/_/g, " ")}</span>;
}

createRoot(document.getElementById("root")!).render(<App />);
