import { useEffect, useState } from "react";
import CrisisNotice from "../components/CrisisNotice";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export default function SafetyPage() {
  const { t } = useTranslation();
  const [msg, setMsg] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [inbox, setInbox] = useState([]);
  const [steps, setSteps] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [contactsLogin, setContactsLogin] = useState(false);
  const [cName, setCName] = useState("");
  const [cPhone, setCPhone] = useState("");
  const [cRel, setCRel] = useState("");
  const [docs, setDocs] = useState([]);
  const [vaultError, setVaultError] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [openDoc, setOpenDoc] = useState(null);

  async function loadContacts() {
    try {
      const d = await api("/api/safety/safe_call_contacts");
      setContacts(d.contacts || []);
      setContactsLogin(false);
    } catch (e) {
      if (e.status === 401) setContactsLogin(true);
    }
  }

  async function loadVault() {
    try {
      const d = await api("/api/safety/document_vault");
      setDocs(d.documents || []);
      setVaultError("");
    } catch (e) {
      if (e.status === 401 || e.status === 402 || e.status === 503) setVaultError(t("safety.vaultUnavailable"));
    }
  }

  useEffect(() => {
    api("/api/safety/private_inbox").then((d) => setInbox(d.messages || [])).catch(() => {});
    api("/api/safety/relapse_protocol/content").then((d) => setSteps(d.steps || [])).catch(() => {});
    loadContacts();
    loadVault();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function markRead(mid) {
    try {
      await api(`/api/safety/private_inbox/${mid}/read`, { method: "POST" });
      setInbox((x) => x.filter((m) => m.id !== mid));
    } catch {}
  }

  async function wipe() { try { await api("/api/safety/data_wipe", { method: "POST" }); setMsg(t("safety.wiped")); } catch (e) { setMsg(e.message); } }

  async function addContact() {
    try {
      await api("/api/safety/safe_call_contacts", { method: "POST", body: { name: cName, phone: cPhone, relationship: cRel } });
      setCName(""); setCPhone(""); setCRel("");
      loadContacts();
    } catch (e) {
      if (e.status === 401) setContactsLogin(true);
      setMsg(e.message);
    }
  }

  async function deleteContact(cid) {
    try {
      await api(`/api/safety/safe_call_contacts/${cid}`, { method: "DELETE" });
      loadContacts();
    } catch (e) { setMsg(e.message); }
  }

  async function addDoc() {
    try {
      await api("/api/safety/document_vault", { method: "POST", body: { title: docTitle, content: docContent } });
      setDocTitle(""); setDocContent("");
      setVaultError("");
      loadVault();
    } catch (e) {
      if (e.status === 401 || e.status === 402 || e.status === 503) setVaultError(t("safety.vaultUnavailable"));
      else setMsg(e.message);
    }
  }

  async function viewDoc(id) {
    if (openDoc && openDoc.id === id) { setOpenDoc(null); return; }
    try {
      const d = await api(`/api/safety/document_vault/${id}`);
      setOpenDoc(d);
      setVaultError("");
    } catch (e) {
      if (e.status === 401 || e.status === 402 || e.status === 503) setVaultError(t("safety.vaultUnavailable"));
      else setMsg(e.message);
    }
  }

  async function deleteDoc(id) {
    try {
      await api(`/api/safety/document_vault/${id}`, { method: "DELETE" });
      if (openDoc && openDoc.id === id) setOpenDoc(null);
      loadVault();
    } catch (e) {
      if (e.status === 401 || e.status === 402 || e.status === 503) setVaultError(t("safety.vaultUnavailable"));
      else setMsg(e.message);
    }
  }

  function stepText(step) {
    if (typeof step === "string") return step;
    if (step && typeof step === "object") return step.title || step.text || String(step);
    return String(step ?? "");
  }

  return (
    <section className="page">
      <h1>{t("nav.safety")}</h1>

      <div className="card">
        <h2>{t("safety.relapseTitle")}</h2>
        <p>{t("safety.relapseDraft")}</p>
        <div className="big-call">
          <a className="big-call" href="tel:988">{t("crisis.call988")}</a>
          <a className="big-call" href="sms:988">{t("crisis.text988")}</a>
          <a className="big-call" href="tel:911">{t("crisis.call911")}</a>
        </div>
        {steps.length > 0 ? (
          <ol>
            {steps.map((s, i) => <li key={i}>{stepText(s)}</li>)}
          </ol>
        ) : (
          <p className="notice">{t("safety.relapsePending")}</p>
        )}
      </div>

      {inbox.length > 0 && <div data-testid="private-inbox"><h2>{t("crisisReply.inboxTitle")}</h2>{inbox.map((m) => <div key={m.id}><CrisisNotice notice={m.message} /><button type="button" className="btn-ghost btn-small" onClick={() => markRead(m.id)}>{t("crisisReply.markRead")}</button></div>)}</div>}

      <div className="section-block">
        <h2 id="safe-contacts">{t("safety.safeContactsTitle")}</h2>
        <p>{t("safety.safeContactsHelp")}</p>
        {contactsLogin && <p className="notice">{t("safety.loginNeeded")}</p>}
        {contacts.length === 0 ? (
          <p>{t("safety.noContacts")}</p>
        ) : (
          <div className="card-list">
            {contacts.map((c) => (
              <div className="contact-row" key={c._id}>
                <span>{c.name}</span>
                {c.relationship && <span className="muted">{c.relationship}</span>}
                <a className="btn-small" href={`tel:${c.phone}`}>{t("safety.call")}</a>
                <button type="button" className="btn-ghost btn-small" onClick={() => deleteContact(c._id)}>{t("safety.deleteContact")}</button>
              </div>
            ))}
          </div>
        )}
        <label>{t("safety.contactName")} <input value={cName} onChange={(e) => setCName(e.target.value)} /></label>
        <label>{t("safety.contactPhone")} <input value={cPhone} onChange={(e) => setCPhone(e.target.value)} /></label>
        <label>{t("safety.contactRelationship")} <input value={cRel} onChange={(e) => setCRel(e.target.value)} /></label>
        <button type="button" onClick={addContact}>{t("safety.addContact")}</button>
      </div>

      <div className="section-block">
        <h2>{t("safety.vaultTitle")}</h2>
        <p>{t("safety.vaultHelp")}</p>
        {vaultError && <p className="notice">{vaultError}</p>}
        {docs.length === 0 ? (
          <p>{t("safety.vaultEmpty")}</p>
        ) : (
          <div className="card-list">
            {docs.map((d) => (
              <div className="vault-row" key={d.id}>
                <span>{d.title}</span>
                <button type="button" className="btn-small" onClick={() => viewDoc(d.id)}>{t("safety.vaultView")}</button>
                <button type="button" className="btn-ghost btn-small" onClick={() => deleteDoc(d.id)}>{t("safety.vaultDelete")}</button>
                {openDoc && openDoc.id === d.id && <pre>{openDoc.content}</pre>}
              </div>
            ))}
          </div>
        )}
        <label>{t("safety.vaultDocTitle")} <input value={docTitle} onChange={(e) => setDocTitle(e.target.value)} /></label>
        <label>{t("safety.vaultDocContent")} <textarea value={docContent} onChange={(e) => setDocContent(e.target.value)} /></label>
        <button type="button" onClick={addDoc}>{t("safety.vaultAdd")}</button>
      </div>

      <div className="section-block">
        <h2>{t("safety.wipeTitle")}</h2>
        <p>{t("safety.wipeHelp")}</p>
        <label><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} /> {t("safety.wipeConfirm")}</label>
        <button type="button" className="btn-danger" disabled={!confirm} onClick={wipe}>{t("safety.wipeButton")}</button>
      </div>

      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
