import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";

const EMPTY_VIS = { milestones: false, appointments: false, portfolio: false };

function memberLabel(m) {
  if (typeof m === "string" || typeof m === "number") return String(m);
  if (m && typeof m === "object") return m.handle || m.name || m.id || m._id || "";
  return String(m ?? "");
}

export default function FamilyPage() {
  const { t } = useTranslation();
  const [vis, setVis] = useState(EMPTY_VIS);
  const [members, setMembers] = useState([]);
  const [handle, setHandle] = useState("");
  const [msg, setMsg] = useState("");
  const [loginNeeded, setLoginNeeded] = useState(false);
  const [memberHandle, setMemberHandle] = useState("");
  const [sharedItems, setSharedItems] = useState(null);

  async function load() {
    try {
      const d = await api("/api/family/family_mode/visibility");
      setVis({ ...EMPTY_VIS, ...(d.visibility || {}) });
      setMembers(d.family_members || []);
      setLoginNeeded(false);
    } catch {
      setLoginNeeded(true);
    }
  }

  useEffect(() => { load(); }, []);

  async function save() {
    try {
      const d = await api("/api/family/family_mode/visibility", {
        method: "PUT",
        body: { milestones: !!vis.milestones, appointments: !!vis.appointments, portfolio: !!vis.portfolio },
      });
      if (d.visibility) setVis({ ...EMPTY_VIS, ...d.visibility });
      setMsg(t("family.saved"));
    } catch (e) {
      if (e.status === 401) setLoginNeeded(true);
      setMsg(e.message);
    }
  }

  async function approve() {
    if (!handle.trim()) return;
    try {
      const d = await api("/api/family/family_mode/family_members", {
        method: "POST",
        body: { family_handle: handle.trim() },
      });
      if (Array.isArray(d.family_members)) setMembers(d.family_members);
      else await load();
      setHandle("");
      setMsg(t("family.memberAdded"));
    } catch (e) {
      if (e.status === 401) setLoginNeeded(true);
      setMsg(e.message);
    }
  }

  async function viewShared() {
    if (!memberHandle.trim()) return;
    try {
      const d = await api(`/api/journey/journey_portfolio/family?member_handle=${encodeURIComponent(memberHandle.trim())}`);
      setSharedItems(d.items || []);
    } catch {
      setSharedItems([]);
    }
  }

  return (
    <section className="page">
      <h1>{t("nav.family")}</h1>
      <p>{t("family.help")}</p>
      <p>{t("family.defaultsOff")}</p>

      {loginNeeded && (
        <p className="notice">
          {t("family.loginNeeded")} <Link to="/settings">{t("nav.platform")}</Link>
        </p>
      )}

      <div className="card">
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={!!vis.milestones}
            onChange={(e) => setVis((v) => ({ ...v, milestones: e.target.checked }))}
          />{" "}
          {t("family.shareMilestones")}
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={!!vis.appointments}
            onChange={(e) => setVis((v) => ({ ...v, appointments: e.target.checked }))}
          />{" "}
          {t("family.shareAppointments")}
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={!!vis.portfolio}
            onChange={(e) => setVis((v) => ({ ...v, portfolio: e.target.checked }))}
          />{" "}
          {t("family.sharePortfolio")}
        </label>
        <button type="button" onClick={save}>{t("family.save")}</button>
        <p className="notice">{t("family.revokeNote")}</p>
      </div>

      <div className="card">
        <h2>{t("family.membersTitle")}</h2>
        {members.length === 0 ? (
          <p>{t("family.noMembers")}</p>
        ) : (
          <div className="card-list">
            {members.map((m, i) => (
              <div className="member-row" key={`${memberLabel(m)}-${i}`}>{memberLabel(m)}</div>
            ))}
          </div>
        )}
        <p>{t("family.approveHelp")}</p>
        <label>
          {t("family.memberHandle")}{" "}
          <input value={handle} onChange={(e) => setHandle(e.target.value)} />
        </label>
        <button type="button" onClick={approve}>{t("family.approve")}</button>
      </div>

      <div className="card">
        <h2>{t("gap.familyViewTitle")}</h2>
        <p>{t("gap.familyViewHelp")}</p>
        <label>
          {t("family.memberHandle")}{" "}
          <input value={memberHandle} onChange={(e) => setMemberHandle(e.target.value)} />
        </label>
        <button type="button" onClick={viewShared}>{t("gap.familyViewBtn")}</button>
        {sharedItems !== null && (
          sharedItems.length === 0 ? (
            <p>{t("gap.familyEmpty")}</p>
          ) : (
            <div className="card-list">
              {sharedItems.map((it) => (
                <div className="member-row" key={it.id}><strong>{it.title}</strong>{it.story ? ` — ${it.story}` : ""}</div>
              ))}
            </div>
          )
        )}
      </div>

      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
