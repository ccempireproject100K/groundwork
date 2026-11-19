import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import ReadAloud from "../components/ReadAloud";
import CrisisNotice from "../components/CrisisNotice";
export default function CommunityPage() {
  const { t } = useTranslation();
  const [posts, setPosts] = useState([]);
  const [body, setBody] = useState("");
  const [anon, setAnon] = useState(false);
  const [msg, setMsg] = useState("");
  const [notice, setNotice] = useState(null);
  const [recipient, setRecipient] = useState("");
  const [dm, setDm] = useState("");
  const [eventTitle, setEventTitle] = useState("");
  const [groupName, setGroupName] = useState("");
  const [qa, setQa] = useState("");
  const [questions, setQuestions] = useState([]);
  const [events, setEvents] = useState([]);
  const [groups, setGroups] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [meetingTitle, setMeetingTitle] = useState("");
  const [inbox, setInbox] = useState([]);
  const [answerText, setAnswerText] = useState({});
  const [media, setMedia] = useState([]);
  async function load() { try { setPosts((await api("/api/community/community_feed/posts")).posts || []); } catch {} }
  async function loadQa() { try { setQuestions((await api("/api/community/anonymous_qa/questions")).questions || []); } catch {} }
  async function loadEvents() { try { setEvents((await api("/api/community/events")).events || []); } catch {} }
  async function loadGroups() { try { setGroups((await api("/api/community/program_groups")).groups || []); } catch {} }
  async function loadMeetings() { try { setMeetings((await api("/api/community/virtual_meetings")).meetings || []); } catch {} }
  async function loadInbox() { try { setInbox((await api("/api/community/peer_messaging/messages")).messages || []); } catch {} }
  async function loadMedia() { try { setMedia((await api("/api/community/media_posts")).media || []); } catch {} }
  useEffect(() => { load(); loadQa(); loadEvents(); loadGroups(); loadMeetings(); loadInbox(); loadMedia(); }, []);
  async function post() { try { const r = await api("/api/community/community_feed/posts", { method: "POST", body: { body, anonymous: anon } }); setNotice(r.private_notice || null); setBody(""); load(); } catch (e) { setMsg(e.message); } }
  async function sendDm() { try { const r = await api("/api/community/peer_messaging/messages", { method: "POST", body: { recipient_id: recipient, body: dm } }); setMsg(t("community.dmSent")); if (r.recipient?.phone) setMsg("phone exposed"); loadInbox(); } catch (e) { setMsg(e.message); } }
  async function postEvent() { try { await api("/api/community/events", { method: "POST", body: { title: eventTitle } }); setEventTitle(""); setMsg("✓"); loadEvents(); } catch (e) { setMsg(e.message); } }
  async function rsvp(eid) { try { const r = await api(`/api/community/events/${eid}/rsvp`, { method: "POST" }); setMsg(`${t("gap.rsvp")}: ${r.count} ${t("gap.going")}`); } catch (e) { setMsg(e.message); } }
  async function postGroup() { try { await api("/api/community/program_groups", { method: "POST", body: { name: groupName } }); setGroupName(""); setMsg("✓"); loadGroups(); } catch (e) { setMsg(e.message); } }
  async function joinGroup(gid) { try { await api(`/api/community/program_groups/${gid}/join`, { method: "POST" }); setMsg("✓"); loadGroups(); } catch (e) { setMsg(e.message); } }
  async function createMeeting() { try { await api("/api/community/virtual_meetings", { method: "POST", body: { title: meetingTitle } }); setMeetingTitle(""); setMsg("✓"); loadMeetings(); } catch (e) { setMsg(e.message); } }
  async function askQa() { try { const r = await api("/api/community/anonymous_qa/questions", { method: "POST", body: { body: qa } }); setNotice(r.private_notice || null); setQa(""); setMsg("✓"); loadQa(); } catch (e) { setMsg(e.message); } }
  async function answerQa(qid) {
    const text = (answerText[qid] || "").trim();
    if (!text) return;
    try { const r = await api(`/api/community/anonymous_qa/questions/${qid}/answers`, { method: "POST", body: { body: text } }); setNotice(r.private_notice || null); setAnswerText((x) => ({ ...x, [qid]: "" })); loadQa(); }
    catch (e) { setMsg(e.message); }
  }
  async function upload(kind, fid, file) {
    if (!file) return;
    const buf = await file.arrayBuffer();
    let bin = ""; const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    try { await api(`/api/community/${fid}`, { method: "POST", body: { filename: file.name, content_type: file.type, data_b64: btoa(bin), caption: "" } }); setMsg("✓"); loadMedia(); }
    catch (e) { setMsg(e.message); }
  }
  return (
    <section>
      <h1>{t("nav.community")}</h1>
      <h2>{t("community.feedTitle")}</h2>
      <label>{t("community.postBody")} <textarea value={body} onChange={(e) => setBody(e.target.value)} /></label>
      <label><input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} /> {t("community.anonymous")}</label>
      <button type="button" onClick={post}>{t("community.post")}</button>
      <CrisisNotice notice={notice} />
      <ul>{posts.map((p, i) => <li key={p._id || i}>{p.body} — {typeof p.author === "object" ? p.author.display : p.author_handle || ""}</li>)}</ul>
      <h2>{t("community.dmTitle")}</h2>
      <p>{t("community.noPhone")}</p>
      <label>{t("community.recipient")} <input value={recipient} onChange={(e) => setRecipient(e.target.value)} /></label>
      <label>{t("community.message")} <input value={dm} onChange={(e) => setDm(e.target.value)} /></label>
      <button type="button" onClick={sendDm}>{t("community.send")}</button>
      <div data-testid="inbox-section"><h3>{t("gap.inboxTitle")}</h3>
        {inbox.length === 0 ? <p>{t("gap.inboxEmpty")}</p> : <ul>{inbox.map((m, i) => <li key={m._id || i}>{m.body}</li>)}</ul>}</div>
      <div data-testid="events-section"><h2>{t("phase3.eventsTitle")}</h2><ReadAloud text={t("phase3.eventsTitle")} />
        <label>{t("phase3.eventsTitle")} <input value={eventTitle} onChange={(e) => setEventTitle(e.target.value)} /></label>
        <button type="button" onClick={postEvent}>{t("phase3.postEvent")}</button>
        {events.length === 0 ? <p>{t("gap.eventsEmpty")}</p> : <ul>{events.map((ev) => <li key={ev._id}>{ev.title}{ev.on ? ` — ${ev.on}` : ""}{ev.city ? `, ${ev.city}` : ""} <button type="button" onClick={() => rsvp(ev._id)}>{t("gap.rsvp")}</button></li>)}</ul>}</div>
      <div data-testid="groups-section"><h2>{t("phase3.groupsTitle")}</h2><ReadAloud text={t("phase3.groupsTitle")} />
        <label>{t("phase3.groupsTitle")} <input value={groupName} onChange={(e) => setGroupName(e.target.value)} /></label>
        <button type="button" onClick={postGroup}>{t("phase3.createGroup")}</button>
        {groups.length === 0 ? <p>{t("gap.groupsEmpty")}</p> : <ul>{groups.map((g) => <li key={g._id}>{g.name} — {g.program} ({g.members ?? 0}) <button type="button" onClick={() => joinGroup(g._id)}>{t("phase3.join")}</button></li>)}</ul>}</div>
      <div data-testid="meetings-section"><h2>{t("phase3.meetingsTitle")}</h2><ReadAloud text={t("phase3.meetingsTitle")} />
        <label>{t("phase3.meetingsTitle")} <input value={meetingTitle} onChange={(e) => setMeetingTitle(e.target.value)} /></label>
        <button type="button" onClick={createMeeting}>{t("phase3.createMeeting")}</button>
        {meetings.length === 0 ? <p>{t("gap.meetingsEmpty")}</p> : <ul>{meetings.map((m) => <li key={m._id}>{m.title} — {t("gap.meetingRoom")}: {m.room}</li>)}</ul>}</div>
      <div data-testid="media-section"><h2>{t("phase3.mediaTitle")}</h2><ReadAloud text={t("phase3.mediaTitle")} />
        <label>{t("phase3.photo")} <input type="file" accept="image/*" onChange={(e) => upload("photo", "photo_posts", e.target.files[0])} /></label>
        <label>{t("phase3.video")} <input type="file" accept="video/*" onChange={(e) => upload("video", "video_posts", e.target.files[0])} /></label>
        <label>{t("phase3.voice")} <input type="file" accept="audio/*" onChange={(e) => upload("voice", "voice_notes", e.target.files[0])} /></label>
        <h3>{t("gap.mediaMine")}</h3>
        {media.length === 0 ? <p>{t("gap.mediaEmpty")}</p> : <ul>{media.map((m, i) => <li key={m._id || i}>{m.kind}: {m.caption || m.filename || ""}</li>)}</ul>}</div>
      <div data-testid="qa-section"><h2>{t("phase3.qaTitle")}</h2><p>{t("phase3.qaHelp")}</p><ReadAloud text={t("phase3.qaHelp")} />
        <label>{t("phase3.qaTitle")} <textarea value={qa} onChange={(e) => setQa(e.target.value)} /></label>
        <button type="button" onClick={askQa}>{t("phase3.ask")}</button>
        <ul>{questions.map((q, i) => (
          <li key={q.id || i}>{q.body}
            {(q.answers || []).length > 0 && <><h4>{t("gap.answersTitle")}</h4><ul>{q.answers.map((a, j) => <li key={a.id || j}>{a.body}</li>)}</ul></>}
            <label>{t("phase3.answer")} <input value={answerText[q.id] || ""} onChange={(e) => setAnswerText((x) => ({ ...x, [q.id]: e.target.value }))} /></label>
            <button type="button" onClick={() => answerQa(q.id)}>{t("phase3.answerBtn")}</button>
          </li>))}</ul></div>
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
