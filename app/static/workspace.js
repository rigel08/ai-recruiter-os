"use strict";

// Call notes, client submissions and saved sessions. Uses the names app.js defines
// ($, el, lastResult, baseResult, clarifications, render, statusChip, stepBadge, askText, factsCell, ...).

const SOURCE_LABELS = { resume: "Resume", recruiter_confirmed: "Confirmed on call", recruiter_entered: "From recruiter" };
const CALL_FIELDS = [
  ["phone", "Phone number", "text", ""],
  ["total_experience", "Total experience", "number", "years"],
  ["notice_period", "Notice period", "number", "days"],
  ["current_ctc", "Current CTC", "number", "LPA"],
  ["expected_ctc", "Expected CTC", "number", "LPA"],
  ["current_location", "Current location", "text", ""],
  ["preferred_location", "Preferred location", "text", ""],
];
const NUMBER_LIMITS = { total_experience: [0, 50, 0.1], notice_period: [0, 365, 1], current_ctc: [0.5, 500, 0.1], expected_ctc: [0.5, 500, 0.1] };
const QUESTIONS = {
  "Phone number": "A phone number to reach you on",
  "Total experience": "Your total years of experience",
  "Notice period": "Your notice period (or your last working day, if you are serving notice)",
  "Current CTC": "Your current CTC",
  "Expected CTC": "Your expected CTC",
  "Current location": "Your current location",
};

const sourceTag = (source) => el("span", { class: `src-tag ${source}` }, SOURCE_LABELS[source]);
const displayName = (c) => c.name || c.file_name;
const jobTitle = () => (($("job-description").value || "").split("\n").map((line) => line.trim()).find(Boolean) || "the role").slice(0, 80);

async function postJson(url, body) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? detail : "That couldn't be done. Check the entries and try again.");
  }
  return data;
}

// ---------- The information column: value in use, where it came from, and what the resume says ----------

function infoCell(c) {
  const e = c.evaluation;
  const cell = el("td", { class: "facts" });
  cell.append(el("div", { class: "stated" },
    el("strong", {}, `${e.completeness.stated} of ${e.completeness.total}`), " tracker fields known"));

  const list = el("dl");
  for (const [key, label] of FACTS) {
    const r = c.resolved[key];
    const resume = c.facts[key];
    if (r.display) {
      const value = el("dd", {}, r.display, sourceTag(r.source));
      if (r.source === "resume" && resume && resume.confirm) value.append(el("span", { class: "check" }, "check"));
      // The resume's own value stays visible whenever the one in use didn't come from it.
      if (r.source === "recruiter_entered" && r.resume_display) value.append(el("span", { class: "was" }, `Resume says: ${r.resume_display}`));
      list.append(el("dt", {}, label), value);
    } else if (resume) {
      list.append(el("dt", {}, label), el("dd", { class: "unclear" }, resume.display, sourceTag("resume")));
    }
  }
  if (list.children.length) cell.append(list);
  else cell.append(el("span", { class: "hint" }, "Nothing known yet."));
  if (c.to_ask.length) cell.append(el("p", { class: "ask" }, el("strong", {}, "Still to ask: "), askText(c.to_ask)));
  if (c.remarks) cell.append(el("p", { class: "reason" }, el("strong", {}, "Your notes: "), c.remarks));
  const evidence = factsCell(c).querySelector("details");
  if (evidence) cell.append(evidence);

  const answered = Object.keys((clarifications[c.file_name] || {}).answers || {}).length;
  const open = el("button", { type: "button", class: "secondary small" }, answered ? "Edit call notes" : "Record call answers");
  open.addEventListener("click", () => openCallNotes(c.file_name));
  cell.append(open);
  return cell;
}

// ---------- Call notes: record answers, review what changes, then accept ----------

const callDialog = $("call-dialog");

function messageFor(c) {
  const items = c.to_ask.map((item) => QUESTIONS[item.split(": ")[0]]).filter(Boolean);
  if (!items.length) return "";
  const first = displayName(c).split(" ")[0];
  return `Hi ${first}, thank you for your interest in the ${jobTitle()} role. To take your profile forward, could you confirm:\n` +
    items.map((item, index) => `${index + 1}. ${item}`).join("\n") + "\nThank you.";
}

function openCallNotes(fileName) {
  const c = lastResult.candidates.find((candidate) => candidate.file_name === fileName);
  const saved = clarifications[fileName] || { answers: {}, remarks: "" };
  const controls = {};

  const close = el("button", { type: "button", class: "secondary small", style: "margin: 0" }, "Close");
  close.addEventListener("click", () => callDialog.close());
  const head = el("div", { class: "sheet-head" },
    el("div", {}, el("h2", { id: "call-title" }, `Call notes: ${displayName(c)}`),
      el("div", { class: "reason" }, "What you record here is kept apart from the resume. The resume's own values are never changed.")),
    close);

  const body = el("div", { class: "sheet-body" });

  // 1. What to ask, ready to send by hand.
  const message = messageFor(c);
  if (message) {
    const draft = el("textarea", { "aria-label": "Message to the candidate" });
    draft.value = message;
    const copy = el("button", { type: "button", class: "secondary small" }, "Copy message");
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(draft.value); copy.textContent = "Copied"; } catch { draft.select(); copy.textContent = "Select and copy by hand"; }
      setTimeout(() => { copy.textContent = "Copy message"; }, 2000);
    });
    body.append(el("h3", {}, "1. Ask"),
      el("p", { class: "reason" }, "A message you can send yourself on WhatsApp or email. Nothing is sent from here."), draft, copy);
  }

  // 2. Paste what came back; it fills the boxes below for you to check.
  const reply = el("textarea", { "aria-label": "The candidate's reply", placeholder: "e.g. NP 30 days, CCTC 14, ECTC 18, currently in Hyderabad" });
  const readStatus = el("span", { class: "hint", role: "status" });
  const read = el("button", { type: "button", class: "secondary small" }, "Read reply into the boxes below");
  read.addEventListener("click", async () => {
    if (!reply.value.trim()) { readStatus.textContent = " Paste the reply first."; return; }
    try {
      const reading = await postJson("/api/clarifications/read-reply", { text: reply.value });
      const fields = Object.keys(reading.found);
      for (const field of fields) {
        const control = controls[field];
        control.state.value = "answered";
        control.input.value = reading.found[field].value;
        control.input.classList.add("from-reply");
        control.input.title = `Read from: “${reading.found[field].quote}”`;
        control.sync();
      }
      readStatus.textContent = fields.length
        ? ` Filled ${fields.length} box${fields.length === 1 ? "" : "es"} (outlined). Check each one before you review.`
        : " Nothing could be read from that. Fill the boxes in by hand.";
    } catch (error) { readStatus.textContent = " " + error.message; }
  });
  body.append(el("h3", {}, message ? "2. Paste the reply (optional)" : "Paste the candidate's reply (optional)"), reply,
    el("div", {}, read, readStatus));

  // 3. One row per detail: what the resume says, and what the candidate said.
  const rows = CALL_FIELDS.map(([field, label, type, unit]) => {
    const resume = c.facts[field];
    const current = saved.answers[field];
    const state = el("select", { "aria-label": `${label}: what happened on the call` },
      el("option", { value: "" }, "Not recorded"),
      el("option", { value: "confirmed" }, "Confirmed as on the resume"),
      el("option", { value: "answered" }, "Candidate said…"),
      el("option", { value: "pending" }, "Asked, waiting for an answer"),
      el("option", { value: "not_applicable" }, "Not applicable"));
    if (!resume || resume.value === null) state.querySelector('[value="confirmed"]').disabled = true;
    const input = el("input", { type, "aria-label": `${label}${unit ? " in " + unit : ""}`, placeholder: unit ? `in ${unit}` : label });
    if (type === "number") {
      const [min, max, step] = NUMBER_LIMITS[field];
      input.min = min; input.max = max; input.step = step;
    } else {
      input.maxLength = 80;
    }
    state.value = current ? current.state : "";
    if (current && current.state === "answered") input.value = current.value;
    const sync = () => { input.hidden = state.value !== "answered"; };
    state.addEventListener("change", () => { sync(); if (state.value === "answered") input.focus(); });
    sync();
    controls[field] = { state, input, sync, label };
    const onResume = resume
      ? el("td", {}, resume.display, resume.confirm ? el("span", { class: "check" }, "check") : null,
        el("div", { class: "reason" }, `“${resume.quote}”`))
      : el("td", { class: "hint" }, "Not on the resume");
    return el("tr", {}, el("th", { scope: "row" }, label, unit ? el("div", { class: "hint" }, unit) : null), onResume, el("td", {}, state, input));
  });
  body.append(el("h3", {}, message ? "3. Record the answers" : "Record the answers"),
    el("div", { class: "table-wrap" }, el("table", { class: "answers" },
      el("thead", {}, el("tr", {}, el("th", {}, "Detail"), el("th", {}, "On the resume"), el("th", {}, "On the call"))),
      el("tbody", {}, ...rows))));

  const remarks = el("textarea", { "aria-label": "Your notes about this candidate", maxlength: "2000",
    placeholder: "Anything worth keeping: reason for change, availability for interviews, concerns" });
  remarks.value = saved.remarks || "";
  body.append(el("h3", {}, "Your notes"), remarks);

  const problem = el("div", { class: "error", role: "alert", hidden: "" });
  body.append(problem);

  const draftFor = () => {
    const answers = {};
    for (const [field, control] of Object.entries(controls)) {
      if (!control.state.value) continue;
      answers[field] = { state: control.state.value };
      if (control.state.value === "answered") {
        answers[field].value = control.input.type === "number" && control.input.value !== "" ? Number(control.input.value) : control.input.value;
      }
    }
    return { answers, remarks: remarks.value };
  };

  const review = el("button", { type: "button" }, "Review changes");
  const clear = el("button", { type: "button", class: "secondary" }, "Clear everything recorded");
  clear.addEventListener("click", () => {
    for (const control of Object.values(controls)) { control.state.value = ""; control.input.value = ""; control.input.classList.remove("from-reply"); control.sync(); }
    remarks.value = "";
  });
  review.addEventListener("click", async () => {
    problem.hidden = true;
    const draft = { ...clarifications, [fileName]: draftFor() };
    if (!Object.keys(draft[fileName].answers).length && !draft[fileName].remarks.trim()) delete draft[fileName];
    review.disabled = true;
    try {
      const updated = await postJson("/api/clarifications/apply", { result: baseResult, clarifications: draft });
      showReview(c, updated, draft);
    } catch (error) {
      problem.textContent = error.message;
      problem.hidden = false;
    } finally { review.disabled = false; }
  });

  callDialog.replaceChildren(head, body, el("div", { class: "sheet-foot" }, clear, review));
  if (!callDialog.open) callDialog.showModal();
}

// Shows what would change for this candidate. Nothing is applied until "Accept".
function showReview(before, updated, draft) {
  const after = updated.candidates.find((candidate) => candidate.file_name === before.file_name);
  const changes = [];
  for (const [field, label] of CALL_FIELDS) {
    const was = before.resolved[field], now = after.resolved[field];
    if (was.display === now.display && was.source === now.source && was.state === now.state) continue;
    const item = el("li", {}, el("strong", {}, `${label}: `), was.display || "Unknown", el("span", { class: "arrow" }, "→"), now.display || "Unknown");
    if (now.display) item.append(sourceTag(now.source));
    if (now.state === "pending") item.append(el("span", { class: "hint" }, " (asked, waiting)"));
    if (now.state === "not_applicable") item.append(el("span", { class: "hint" }, " (not applicable)"));
    if (now.source === "recruiter_entered" && now.resume_display) item.append(el("span", { class: "was" }, `The resume still says: ${now.resume_display}`));
    changes.push(item);
  }
  const checksOf = (c) => [...(c.evaluation.skills.experience ? [c.evaluation.skills.experience] : []), ...c.evaluation.constraints.checks];
  const checkChanges = [];
  const oldChecks = Object.fromEntries(checksOf(before).map((check) => [check.requirement, check]));
  for (const check of checksOf(after)) {
    const was = oldChecks[check.requirement];
    if (was && was.status === check.status && was.reason === check.reason) continue;
    checkChanges.push(el("li", {}, el("strong", {}, `${check.label}: `), was ? statusChip(was.status) : "Not checked",
      el("span", { class: "arrow" }, "→"), statusChip(check.status), el("div", { class: "reason" }, check.reason)));
  }

  const body = el("div", { class: "sheet-body" });
  body.append(el("h3", {}, "What will change"));
  if (!changes.length && !checkChanges.length && (before.remarks || "") === (after.remarks || "")) {
    body.append(el("p", { class: "notice" }, "Nothing changes. Go back to record an answer, or close."));
  }
  if (changes.length) body.append(el("p", { class: "reason" }, "Details in use:"), el("ul", { class: "change-list" }, ...changes));
  if (checkChanges.length) body.append(el("p", { class: "reason" }, "Checks against the client's requirements:"), el("ul", { class: "change-list" }, ...checkChanges));
  const stepWas = before.evaluation.next_step, stepNow = after.evaluation.next_step;
  body.append(el("p", { style: "margin: 14px 0 0" }, el("strong", {}, "Next step: "), stepBadge(stepWas),
    el("span", { class: "arrow" }, "→"), stepBadge(stepNow)), el("p", { class: "reason" }, stepNow.reason));
  if ((before.remarks || "") !== (after.remarks || "")) body.append(el("p", { class: "reason" }, el("strong", {}, "Your notes: "), after.remarks || "(cleared)"));
  body.append(el("p", { class: "notice", style: "margin-top: 14px" },
    "Accepting re-evaluates this candidate with these details. The resume evidence stays as it is, and you can edit or clear the answers later."));

  const back = el("button", { type: "button", class: "secondary" }, "Back to editing");
  // Reopen the editor showing the draft, without committing it.
  back.addEventListener("click", () => {
    const committed = clarifications;
    clarifications = draft;
    openCallNotes(before.file_name);
    clarifications = committed;
  });
  const accept = el("button", { type: "button" }, "Accept and re-evaluate");
  accept.addEventListener("click", () => {
    clarifications = draft;
    lastResult = updated;
    callDialog.close();
    render();
    if (typeof sessionChanged === "function") sessionChanged();
  });
  const head = el("div", { class: "sheet-head" }, el("div", {}, el("h2", { id: "call-title" }, `Review: ${displayName(before)}`),
    el("div", { class: "reason" }, "Check this before it is applied.")));
  callDialog.replaceChildren(head, body, el("div", { class: "sheet-foot" }, back, accept));
  accept.focus();
}
