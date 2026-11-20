import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import ReadAloud from "../components/ReadAloud";
export default function SupportPage() {
  const { t } = useTranslation();
  const [resources, setResources] = useState([]);
  const [referrals, setReferrals] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [groups, setGroups] = useState([]);
  const [entries, setEntries] = useState([]);
  const [carpoolCount, setCarpoolCount] = useState(null);
  const [city, setCity] = useState("");
  const [meetingId, setMeetingId] = useState("m1");
  const [showFallback, setShowFallback] = useState(true);
  const [msg, setMsg] = useState("");
  const [contact, setContact] = useState("");
  const [contacts, setContacts] = useState([]);
  const [approveBy, setApproveBy] = useState({});
  const [approveRel, setApproveRel] = useState({});
  const [ping, setPing] = useState(null);
  const [pingConfirm, setPingConfirm] = useState(false);
  const [joined, setJoined] = useState(false);
  const [myGroup, setMyGroup] = useState(null);
  const [mentorRole, setMentorRole] = useState("mentee");
  const [mentorTopics, setMentorTopics] = useState("");
  const [mentorBio, setMentorBio] = useState("");
  const [mentors, setMentors] = useState([]);
  const [mentorMsg, setMentorMsg] = useState({});
  const [geoCity, setGeoCity] = useState("");
  const [geoMe, setGeoMe] = useState(null);
  const [geoMembers, setGeoMembers] = useState([]);
  const [rideFrom, setRideFrom] = useState("");
  const [rideTo, setRideTo] = useState("");
  const [rideOn, setRideOn] = useState("");
  const [rideNotes, setRideNotes] = useState("");
  const [rideRequests, setRideRequests] = useState([]);
  const [offerMsg, setOfferMsg] = useState({});
  async function loadMentors() { try { setMentors((await api("/api/support/mentorship/mentors")).mentors || []); } catch {} }
  async function loadGeo() {
    try { setGeoMe(await api("/api/support/geolocation/me")); } catch {}
    try { setGeoMembers((await api("/api/support/geolocation/members")).members || []); } catch {}
  }
  async function loadRides() { try { setRideRequests((await api("/api/support/needs_a_ride/requests")).requests || []); } catch {} }
  async function loadContacts() { try { setContacts((await api("/api/support/needs_a_ride/family/contacts")).contacts || []); } catch {} }
  async function loadGroup() { try { const d = await api("/api/support/accountability_partners/my_group"); setMyGroup(d); if (d.group) setJoined(true); } catch {} }
  useEffect(() => {
    api("/api/support/resource_directory").then((d) => setResources(d.resources || [])).catch(() => {});
    api("/api/support/counseling_referrals").then((d) => setReferrals(d.referrals || [])).catch(() => {});
    api("/api/support/twelve_step_locator").then((d) => setMeetings(d.meetings || [])).catch(() => {});
    api("/api/support/community_groups_directory").then((d) => setGroups(d.groups || [])).catch(() => {});
    loadMentors(); loadGeo(); loadRides(); loadContacts(); loadGroup();
  }, []);
  useEffect(() => {
    api(`/api/support/carpool_board/entries?meeting_id=${meetingId}`).then((d) => setEntries(d.entries || [])).catch(() => {});
    api(`/api/support/carpool_board/matches?meeting_id=${meetingId}`).then((d) => setCarpoolCount(d.carpool_count)).catch(() => setCarpoolCount(null));
    api(`/api/support/needs_a_ride/fallback?meeting_id=${meetingId}`).then((d) => setShowFallback(d.show_fallback)).catch(() => setShowFallback(true));
  }, [meetingId, msg]);
  async function joinCarpool() {
    try { await api("/api/support/carpool_board/entries", { method: "POST", body: { city: city || "Fort Worth", meeting_source: "twelve_step", meeting_id: meetingId } }); setMsg("ok"); }
    catch (e) { setMsg(e.message); }
  }
  async function leaveCarpool() {
    try { await api("/api/support/carpool_board/entries", { method: "POST", body: { city: city || "Fort Worth", meeting_source: "twelve_step", meeting_id: meetingId, opt_in: false } }); setMsg("ok"); }
    catch (e) { setMsg(e.message); }
  }
  async function joinPartners() { try { await api("/api/support/accountability_partners/join", { method: "POST", body: { goals: [] } }); setJoined(true); loadGroup(); } catch { setJoined(true); } }
  async function addContact() {
    try { const c = await api("/api/support/needs_a_ride/family/contacts", { method: "POST", body: { label: contact } }); setContacts((x) => [...x, c]); setContact(""); }
    catch (e) { setMsg(e.message); }
  }
  async function approveContact(c) {
    try { const d = await api(`/api/support/needs_a_ride/family/contacts/${c._id}/approve`, { method: "POST", body: { approved_by: approveBy[c._id] || "", relationship: approveRel[c._id] || "" } }); setContacts((x) => x.map((y) => (y._id === c._id ? d : y))); }
    catch (e) { setMsg(e.message); }
  }
  async function pingStart() { try { setPing(await api("/api/support/needs_a_ride/family/ping/start", { method: "POST" })); } catch (e) { setMsg(e.message); } }
  async function pingNext() {
    if (!ping) return;
    try { setPing(await api("/api/support/needs_a_ride/family/ping/next", { method: "POST", body: { session_id: ping.session_id, confirm: pingConfirm } })); setPingConfirm(false); }
    catch (e) { setMsg(e.message); }
  }
  async function saveMentorProfile() {
    try { await api("/api/support/mentorship/profile", { method: "POST", body: { role: mentorRole, topics: mentorTopics.split(",").map((s) => s.trim()).filter(Boolean), bio: mentorBio } }); setMsg(t("gap.savedGeneric")); loadMentors(); }
    catch (e) { setMsg(e.message); }
  }
  async function requestMentor(m) {
    try { await api("/api/support/mentorship/requests", { method: "POST", body: { mentor_handle: m.handle, message: mentorMsg[m.handle] || "I would like to ask about mentorship." } }); setMsg(t("gap.mentorSent")); }
    catch (e) { setMsg(e.message); }
  }
  async function shareCity() { try { setGeoMe(await api("/api/support/geolocation", { method: "POST", body: { city: geoCity, opt_in: true } })); loadGeo(); } catch (e) { setMsg(e.message); } }
  async function stopSharing() { try { setGeoMe(await api("/api/support/geolocation", { method: "DELETE" })); loadGeo(); } catch (e) { setMsg(e.message); } }
  async function askRide() {
    try { await api("/api/support/needs_a_ride/requests", { method: "POST", body: { from_city: rideFrom, to_city: rideTo, on: rideOn, notes: rideNotes } }); setRideNotes(""); loadRides(); }
    catch (e) { setMsg(e.message); }
  }
  async function offerRide(r) {
    try { await api("/api/support/needs_a_ride/offers", { method: "POST", body: { request_id: r._id, message: offerMsg[r._id] || "I can offer a ride." } }); setMsg(t("gap.offerSent")); }
    catch (e) { setMsg(e.message); }
  }
  return (
    <section>
      <h1>{t("nav.support")}</h1>
      <h2>{t("support.resourcesTitle")}</h2>
      <p>{t("support.resourcesNote")}</p>
      <ul>{resources.map((r) => <li key={r.id}>{r.name} ({r.category}) <ReadAloud text={r.name} /></li>)}</ul>
      <div data-testid="counseling-section"><h2>{t("gap.counselingTitle")}</h2>
        <ul>{referrals.map((r) => <li key={r.id}>{r.name} ({r.category})</li>)}</ul></div>
      <h2>{t("support.meetingsTitle")}</h2>
      <ul>{meetings.map((m) => <li key={m.id}>{m.name} — {m.program}, {m.day} {m.time}, {m.city}</li>)}</ul>
      <div data-testid="mentorship-section"><h2>{t("phase3.mentorshipTitle")}</h2><p>{t("phase3.mentorshipHelp")}</p><ReadAloud text={t("phase3.mentorshipHelp")} />
        <label>{t("gap.mentorRole")} <select value={mentorRole} onChange={(e) => setMentorRole(e.target.value)}><option value="mentor">{t("gap.mentorRoleMentor")}</option><option value="mentee">{t("gap.mentorRoleMentee")}</option></select></label>
        <label>{t("gap.mentorTopics")} <input value={mentorTopics} onChange={(e) => setMentorTopics(e.target.value)} /></label>
        <label>{t("gap.mentorBio")} <input value={mentorBio} onChange={(e) => setMentorBio(e.target.value)} /></label>
        <button type="button" onClick={saveMentorProfile}>{t("gap.mentorSave")}</button>
        <h3>{t("gap.mentorsTitle")}</h3>
        {mentors.length === 0 ? <p>{t("gap.mentorsEmpty")}</p> : <ul>{mentors.map((m, i) => <li key={m.handle || i}>{m.handle} — {(m.topics || []).join(", ")} {m.bio}
          <label>{t("gap.mentorMessage")} <input value={mentorMsg[m.handle] || ""} onChange={(e) => setMentorMsg((x) => ({ ...x, [m.handle]: e.target.value }))} /></label>
          <button type="button" onClick={() => requestMentor(m)}>{t("gap.mentorSend")}</button></li>)}</ul>}</div>
      <div data-testid="geo-section"><h2>{t("phase3.geoTitle")}</h2><p>{t("phase3.geoHelp")}</p><ReadAloud text={t("phase3.geoHelp")} />
        {geoMe?.opt_in ? <p>{t("gap.geoSharing")}: {geoMe.city}</p> : <p>{t("gap.geoNotSharing")}</p>}
        <label>{t("phase3.city")} <input value={geoCity} onChange={(e) => setGeoCity(e.target.value)} /></label>
        <button type="button" onClick={shareCity}>{t("phase3.shareCity")}</button>
        <button type="button" onClick={stopSharing}>{t("phase3.stopSharing")}</button>
        <h3>{t("gap.geoMembers")}</h3>
        <ul>{geoMembers.map((m, i) => <li key={i}>{m.member?.handle || m.member?.display || ""} — {m.city}</li>)}</ul></div>
      <div data-testid="carpool-section"><h2>{t("phase3.carpoolTitle")}</h2><p>{t("phase3.carpoolHelp")}</p><ReadAloud text={t("phase3.carpoolHelp")} />
        <label>{t("phase3.carpoolCity")} <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Fort Worth" /></label>
        <label>{t("phase3.carpoolMeeting")} <input value={meetingId} onChange={(e) => setMeetingId(e.target.value)} /></label>
        <button type="button" onClick={joinCarpool}>{t("phase3.carpoolJoin")}</button>
        <button type="button" onClick={leaveCarpool}>{t("phase3.carpoolLeave")}</button>
        {carpoolCount !== null && <p>{carpoolCount} {t("phase3.carpoolMatches")}</p>}
        <ul>{entries.map((e, i) => <li key={i}>{e.member?.handle} — {e.city} ({e.meeting_id})</li>)}</ul></div>
      <div data-testid="groups-section"><h2>{t("phase3.groupsTitle2")}</h2><p>{t("phase3.groupsHelp")}</p><ReadAloud text={t("phase3.groupsHelp")} />
        <ul>{groups.map((g) => <li key={g.id}>{g.name} — {g.kind}, {g.city}, {g.meeting_time} <span>{t("phase3.sampleBadge")}</span></li>)}</ul></div>
      {showFallback && (<div data-testid="ride-fallback"><h2>{t("phase3.rideFallbackTitle")}</h2><p>{t("phase3.noCarpoolMatch")}</p><p>{t("phase3.rideFallbackHelp")}</p><ReadAloud text={t("phase3.rideFallbackHelp")} /></div>)}
      <div data-testid="ride-section"><h2>{t("phase3.rideTitle")}</h2><p>{t("phase3.rideHelp")}</p><ReadAloud text={t("phase3.rideHelp")} />
        <label>{t("phase3.from")} <input value={rideFrom} onChange={(e) => setRideFrom(e.target.value)} /></label>
        <label>{t("phase3.to")} <input value={rideTo} onChange={(e) => setRideTo(e.target.value)} /></label>
        <label>{t("gap.rideDate")} <input value={rideOn} onChange={(e) => setRideOn(e.target.value)} /></label>
        <label>{t("gap.rideNotes")} <input value={rideNotes} onChange={(e) => setRideNotes(e.target.value)} /></label>
        <button type="button" onClick={askRide}>{t("phase3.askRide")}</button>
        <h3>{t("gap.rideRequestsTitle")}</h3>
        {rideRequests.length === 0 ? <p>{t("gap.rideEmpty")}</p> : <ul>{rideRequests.map((r) => <li key={r._id}>{r.from_city} → {r.to_city}{r.on ? ` (${r.on})` : ""} — {r.requester?.handle || ""}
          <label>{t("gap.mentorMessage")} <input value={offerMsg[r._id] || ""} onChange={(e) => setOfferMsg((x) => ({ ...x, [r._id]: e.target.value }))} /></label>
          <button type="button" onClick={() => offerRide(r)}>{t("gap.offerRide")}</button></li>)}</ul>}</div>
      <div data-testid="family-ride-section"><h2>{t("phase3.familyRideTitle")}</h2><p>{t("phase3.familyRideHelp")}</p><ReadAloud text={t("phase3.familyRideHelp")} />
        <label>{t("phase3.contactLabel")} <input value={contact} onChange={(e) => setContact(e.target.value)} /></label>
        <button type="button" onClick={addContact}>{t("phase3.addContact")}</button>
        <ul>{contacts.map((c) => <li key={c._id}>{c.label} — {c.verified ? t("phase3.verified") : t("phase3.notAvailable")}{c.quiet_now ? ` · ${t("phase3.quietNow")}` : ""}
          {!c.verified && <span>
            <label>{t("phase3.approvedBy")} <input value={approveBy[c._id] || ""} onChange={(e) => setApproveBy((x) => ({ ...x, [c._id]: e.target.value }))} /></label>
            <label>{t("phase3.relationship")} <input value={approveRel[c._id] || ""} onChange={(e) => setApproveRel((x) => ({ ...x, [c._id]: e.target.value }))} /></label>
            <button type="button" onClick={() => approveContact(c)}>{t("phase3.approveContact")}</button></span>}</li>)}</ul>
        <button type="button" onClick={pingStart}>{t("phase3.pingStart")}</button>
        {ping && <div data-testid="ping-status"><p>{ping.status === "done" ? t("phase3.pingDone") : t("phase3.pingAwaiting")}{ping.contact ? `: ${ping.contact.label}` : ""}</p>
          <label><input type="checkbox" checked={pingConfirm} onChange={(e) => setPingConfirm(e.target.checked)} /> {t("phase3.pingConfirm")}</label>
          <button type="button" onClick={pingNext}>{t("phase3.pingNext")}</button></div>}</div>
      <div data-testid="partners-section"><h2>{t("phase3.partnersTitle")}</h2><p>{t("phase3.partnersHelp")}</p><ReadAloud text={t("phase3.partnersHelp")} />
        <button type="button" onClick={joinPartners}>{t("phase3.joinPartners")}</button>{joined && <p role="status">✓</p>}
        {myGroup?.group ? <p>{t("gap.groupMembers")}: {(myGroup.members || []).map((m) => m.handle || m.display || "").filter(Boolean).join(", ") || "—"}</p> : <p>{t("gap.notGrouped")}</p>}</div>
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
