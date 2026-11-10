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

// ---------- Duplicates and the selection bar ----------

// Shown above the candidates: duplicates within this batch, then people already in other saved sessions.
function duplicateNotes(data) {
  const inBatch = (data.duplicates || []).map((group) => el("p", { class: "notice warn" },
    el("strong", {}, "Possible duplicate: "),
    `${group.file_names.join(" and ")} look like the same person (${group.names[0]}). ${group.reason} Call and submit only one.`));
  return [...inBatch, ...seenNotes()];
}

function selectedCandidates() {
  if (!lastResult || lastResult.hiring_mode !== "experienced") return [];
  return lastResult.candidates.filter((c) => c.status === "ranked" && compared.has(c.file_name));
}

function renderSelection() {
  const chosen = selectedCandidates();
  const isExperienced = lastResult && lastResult.hiring_mode === "experienced";
  $("selection").hidden = !isExperienced;
  if (!isExperienced) return;
  $("selection-count").textContent = chosen.length ? `${chosen.length} selected` : "Tick candidates to compare them or prepare a client submission.";
  $("prepare-submission").disabled = chosen.length === 0;
  $("selection-clear").hidden = chosen.length === 0;
}

$("selection-clear").addEventListener("click", () => { compared.clear(); render(); });

// ---------- Client submission: draft, edit, preview, export ----------

let submission = null;   // { title, includeContact, showSources, order, excluded, profiles, checks, preparedOn }

$("prepare-submission").addEventListener("click", async () => {
  const status = $("selection-status");
  status.textContent = " Preparing…";
  try {
    const draft = await postJson("/api/submissions/draft", {
      result: baseResult, clarifications, file_names: selectedCandidates().map((c) => c.file_name), title: jobTitle() });
    const before = submission;
    const edited = Object.fromEntries(((before && before.profiles) || []).map((profile) => [profile.file_name, profile]));
    submission = {
      title: before ? before.title : draft.title,
      includeContact: before ? before.includeContact : false,   // contact details stay out unless the recruiter turns them on
      showSources: before ? before.showSources : true,
      order: before ? before.order : draft.profiles[0].fields.map((field) => field.key),
      excluded: before ? before.excluded : new Set(),
      preparedOn: draft.prepared_on,
      checks: draft.checks,
      // Keep what the recruiter already wrote for a candidate; refresh everything else.
      profiles: draft.profiles.map((profile) => {
        const old = edited[profile.file_name];
        if (!old) return { ...profile, touched: {} };
        const fields = profile.fields.map((field) => {
          const was = old.fields.find((f) => f.key === field.key);
          return old.touched[field.key] && was ? { ...field, value: was.value, source: was.source } : field;
        });
        return { ...profile, fields, touched: old.touched,
          summary: old.touched.summary ? old.summary : profile.summary,
          remarks: old.touched.remarks ? old.remarks : profile.remarks };
      }),
    };
    status.textContent = "";
    renderSubmission();
    $("submission").scrollIntoView({ behavior: "smooth", block: "start" });
    if (typeof sessionChanged === "function") sessionChanged();
  } catch (error) { status.textContent = " " + error.message; }
});

function submissionDocument() {
  const position = (key) => { const index = submission.order.indexOf(key); return index === -1 ? 999 : index; };
  return {
    title: submission.title,
    prepared_on: submission.preparedOn,
    include_contact: submission.includeContact,
    show_sources: submission.showSources,
    profiles: submission.profiles.map((profile) => ({
      file_name: profile.file_name, name: profile.name, summary: profile.summary, strengths: profile.strengths,
      remarks: profile.remarks, missing: profile.missing, checks: profile.checks,
      fields: [...profile.fields].sort((a, b) => position(a.key) - position(b.key))
        .map((field) => ({ ...field, included: !submission.excluded.has(field.key) })),
    })),
  };
}

const MARKS = { recruiter_confirmed: "confirmed with candidate", recruiter_entered: "from recruiter's call" };

// The client-facing page. It shows only known, included details; contact details only when switched on.
function renderDocument() {
  const doc = submissionDocument();
  const page = el("article", { class: "doc", id: "sub-doc", "aria-label": "Preview of the submission" });
  page.append(el("h2", {}, doc.title || "Candidate profiles"),
    el("p", { class: "prepared" }, `Prepared ${new Date(doc.prepared_on + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })} · ${doc.profiles.length} candidate${doc.profiles.length === 1 ? "" : "s"}`));
  let marked = false;
  doc.profiles.forEach((profile, index) => {
    const block = el("section", { class: "profile" }, el("h3", {}, doc.profiles.length > 1 ? `${index + 1}. ${profile.name}` : profile.name));
    if (profile.summary.trim()) block.append(el("p", { style: "margin: 0" }, profile.summary.trim()));
    const list = el("dl");
    for (const field of profile.fields) {
      if (!field.included || !field.value || (field.contact && !doc.include_contact)) continue;
      const value = el("dd", {}, field.value);
      if (doc.show_sources && MARKS[field.source]) { value.append(el("span", { class: "mark" }, ` (${MARKS[field.source]})`)); marked = true; }
      list.append(el("dt", {}, field.label), value);
    }
    if (list.children.length) block.append(list);
    if (profile.strengths.length) block.append(el("strong", {}, "Strengths for this role"), el("ul", {}, ...profile.strengths.map((item) => el("li", {}, item))));
    if (profile.remarks.trim()) block.append(el("p", { style: "margin: 0" }, el("strong", {}, "Recruiter's remarks: "), profile.remarks.trim()));
    page.append(block);
  });
  if (marked) page.append(el("p", { class: "legend" }, "Details marked in brackets were confirmed with, or provided by, the candidate on a call. All other details are as stated on the candidate's resume."));
  return page;
}

function refreshPreview() {
  $("sub-doc").replaceWith(renderDocument());
  if (typeof sessionChanged === "function") sessionChanged();
}

function renderSubmission() {
  const section = $("submission");
  document.body.classList.toggle("has-submission", Boolean(submission));
  section.hidden = !submission;
  if (!submission) { section.replaceChildren(); return; }

  const close = el("button", { type: "button", class: "secondary" }, "Close submission");
  close.addEventListener("click", () => { submission = null; renderSubmission(); if (typeof sessionChanged === "function") sessionChanged(); });
  const head = el("div", { class: "actions no-print", style: "justify-content: space-between; margin-bottom: 12px" },
    el("h2", { style: "margin: 0; font-size: 18px" }, `Client submission (${submission.profiles.length})`), close);

  // --- options
  const title = el("input", { type: "text", id: "sub-title", maxlength: "200" });
  title.value = submission.title;
  title.addEventListener("input", () => { submission.title = title.value; refreshPreview(); });
  const toggle = (id, text, key) => {
    const box = el("input", { type: "checkbox", id });
    box.checked = submission[key];
    box.addEventListener("change", () => { submission[key] = box.checked; refreshPreview(); });
    return el("label", { class: "mode", for: id, style: "margin: 8px 0 0" }, box, el("span", {}, text));
  };
  const options = el("div", { class: "sub-card" }, el("h3", {}, "The document"),
    el("label", { for: "sub-title" }, "Heading"), title,
    toggle("sub-contact", "Include phone and email (left out unless you tick this)", "includeContact"),
    toggle("sub-sources", "Mark details that came from a call, not the resume", "showSources"));

  // --- which details, in what order (applies to every candidate)
  const labels = Object.fromEntries(submission.profiles[0].fields.map((field) => [field.key, field.label]));
  const contactKeys = new Set(submission.profiles[0].fields.filter((field) => field.contact).map((field) => field.key));
  const fieldList = el("ul", { class: "field-list" });
  const drawFields = () => {
    fieldList.replaceChildren(...submission.order.map((key, index) => {
      const box = el("input", { type: "checkbox" });
      box.checked = !submission.excluded.has(key);
      box.addEventListener("change", () => { if (box.checked) submission.excluded.delete(key); else submission.excluded.add(key); refreshPreview(); });
      const move = (step, symbol, word) => {
        const button = el("button", { type: "button", class: "icon-button", "aria-label": `Move ${labels[key]} ${word}` }, symbol);
        button.disabled = index + step < 0 || index + step >= submission.order.length;
        button.addEventListener("click", () => {
          const order = submission.order;
          [order[index], order[index + step]] = [order[index + step], order[index]];
          drawFields();
          refreshPreview();
          fieldList.children[index + step].querySelector(`button[aria-label$="${word}"]`).focus();
        });
        return button;
      };
      return el("li", {}, el("label", {}, box, labels[key], contactKeys.has(key) ? el("span", { class: "hint" }, "(contact)") : null),
        move(-1, "↑", "up"), move(1, "↓", "down"));
    }));
  };
  drawFields();
  const fieldsCard = el("div", { class: "sub-card" }, el("h3", {}, "Details to include, in order"),
    el("p", { class: "reason" }, "Applies to every candidate. Details that aren't known are left out, never filled in."), fieldList);

  // --- one card per candidate
  const cards = submission.profiles.map((profile, index) => {
    const summary = el("textarea", { maxlength: "3000", id: `sub-summary-${index}` });
    summary.value = profile.summary;
    summary.addEventListener("input", () => { profile.summary = summary.value; profile.touched.summary = true; refreshPreview(); });
    const remarks = el("textarea", { maxlength: "2000", id: `sub-remarks-${index}`, placeholder: "Your recommendation, interview impressions, availability for interviews" });
    remarks.value = profile.remarks;
    remarks.addEventListener("input", () => { profile.remarks = remarks.value; profile.touched.remarks = true; refreshPreview(); });

    const move = (step, symbol, word) => {
      const button = el("button", { type: "button", class: "icon-button", "aria-label": `Move ${profile.name} ${word}` }, symbol);
      button.disabled = index + step < 0 || index + step >= submission.profiles.length;
      button.addEventListener("click", () => {
        const list = submission.profiles;
        [list[index], list[index + step]] = [list[index + step], list[index]];
        renderSubmission();
      });
      return button;
    };
    const remove = el("button", { type: "button", class: "icon-button", "aria-label": `Remove ${profile.name} from the submission` }, "Remove");
    remove.addEventListener("click", () => {
      submission.profiles.splice(index, 1);
      if (!submission.profiles.length) submission = null;
      renderSubmission();
    });

    const card = el("div", { class: "sub-card" },
      el("div", { class: "actions", style: "justify-content: space-between" }, el("h3", {}, `${index + 1}. ${profile.name}`),
        el("span", { class: "actions" }, move(-1, "↑", "up"), move(1, "↓", "down"), remove)));
    if (profile.checks.length) {
      card.append(el("ul", { class: "preflight", "aria-label": "Checks before you send" },
        ...profile.checks.map((check) => el("li", { class: check.level }, check.text))));
    } else {
      card.append(el("p", { class: "reason" }, "No conflicts or unknowns against the client's requirements."));
    }
    if (profile.missing.length) card.append(el("p", { class: "reason" }, el("strong", {}, "Not known, so left out: "), profile.missing.join(", ") + "."));
    card.append(el("label", { for: `sub-summary-${index}` }, "Summary ", el("span", { class: "hint" }, "(a starting point built from known details: rewrite it)")), summary,
      el("label", { for: `sub-remarks-${index}` }, "Your remarks to the client"), remarks);

    // Any detail can be corrected by hand. A changed value is marked as coming from the recruiter.
    const rows = profile.fields.map((field) => {
      const input = el("input", { type: "text", maxlength: "300", "aria-label": `${field.label} for ${profile.name}` });
      input.value = field.value || "";
      input.addEventListener("input", () => {
        field.value = input.value.trim() || null;
        field.source = field.value ? "recruiter_entered" : "unknown";
        profile.touched[field.key] = true;
        refreshPreview();
      });
      return el("tr", {}, el("td", {}, field.label), el("td", { style: "width: 60%" }, input));
    });
    card.append(el("details", {}, el("summary", {}, "Edit this candidate's details"),
      el("p", { class: "reason" }, "A detail you change here is marked as coming from you, not the resume. It changes this document only."),
      el("table", { class: "edit-fields" }, el("tbody", {}, ...rows))));
    return card;
  });

  // --- export
  const status = el("span", { class: "hint", role: "status" });
  const exportButton = (text, action, primary) => {
    const button = el("button", { type: "button", class: primary ? "" : "secondary" }, text);
    button.addEventListener("click", async () => {
      status.textContent = "";
      try { await action(); } catch (error) { status.textContent = " " + error.message; }
    });
    return button;
  };
  const fetchExport = async (format) => {
    const response = await fetch(`/api/submissions/export?format=${format}`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(submissionDocument()) });
    if (!response.ok) throw new Error("The file couldn't be built. Check the entries and try again.");
    return response;
  };
  const save = async (format, fileName) => {
    const link = el("a", { href: URL.createObjectURL(await (await fetchExport(format)).blob()), download: fileName });
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(link.href);
  };
  const conflicts = submission.profiles.reduce((count, profile) => count + profile.checks.filter((check) => check.level === "conflict").length, 0);
  const exports = el("div", { class: "sub-card no-print" }, el("h3", {}, "Send it yourself"),
    el("p", { class: "reason" }, "Nothing is sent from here. Print or save the page, or copy or download the profiles, then send them your usual way."),
    conflicts ? el("p", { class: "notice warn" }, `${conflicts} conflict${conflicts === 1 ? "" : "s"} with the client's requirements above. You can still send; make sure it's deliberate.`) : null,
    el("div", { class: "actions" },
      exportButton("Print or save as PDF", async () => window.print(), true),
      exportButton("Copy as text", async () => {
        const text = await (await fetchExport("text")).text();
        await navigator.clipboard.writeText(text);
        status.textContent = " Copied.";
      }),
      exportButton("Download Excel", () => save("xlsx", "candidate-profiles.xlsx")),
      exportButton("Download CSV", () => save("csv", "candidate-profiles.csv")), status));

  const batch = submission.checks.length
    ? el("ul", { class: "preflight no-print" }, ...submission.checks.map((check) => el("li", { class: check.level }, check.text))) : null;
  const editor = el("div", { class: "no-print" }, options, fieldsCard, ...cards);
  const preview = el("div", {}, el("h3", { class: "no-print", style: "margin: 0 0 8px; font-size: 15px" }, "Preview: what the client sees"), renderDocument(), exports);
  section.replaceChildren(head, ...(batch ? [batch] : []), el("div", { class: "sub-grid" }, editor, preview));
}

// ---------- Saved sessions (stored in a file on this computer, when the app runs locally) ----------

let workspaceInfo = { enabled: false, note: "" };
let currentSession = null;   // { id, name, status } once this evaluation has been saved
let seenElsewhere = [];      // candidates here who are also in another saved session
let savedAt = "";
let saveTimer = null;

const FORM_BOXES = { must_haves: "must-haves", preferred_skills: "preferred-skills", min_experience_years: "min-exp",
  max_experience_years: "max-exp", max_notice_days: "max-notice", max_ctc_lpa: "max-ctc", locations: "locations" };
const SESSION_STATUSES = { open: "Open", submitted: "Submitted to client", on_hold: "On hold", closed: "Closed" };

async function workspaceCall(method, path, body) {
  const options = { method, headers: method === "GET" ? {} : { "X-Workspace": "1" } };
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch("/api/workspace" + path, options);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error((data && typeof data.detail === "string" && data.detail) || "That couldn't be saved. Try again.");
  return data;
}

const clockTime = () => new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const storedSubmission = () => (submission ? { ...submission, excluded: [...submission.excluded] } : null);

// One line per other session, however many people it shares with this one.
function seenNotes() {
  const bySession = new Map();
  for (const seen of seenElsewhere) {
    if (!bySession.has(seen.session_id)) bySession.set(seen.session_id, { ...seen, people: [] });
    const people = bySession.get(seen.session_id).people;
    if (!people.includes(seen.name)) people.push(seen.name);
  }
  return [...bySession.values()].map((group) => {
    const shown = group.people.slice(0, 4).join(", ") + (group.people.length > 4 ? ` and ${group.people.length - 4} more` : "");
    return el("p", { class: "notice warn" }, el("strong", {}, "Seen before: "),
      `${shown} ${group.people.length === 1 ? "is" : "are"} also in your saved session “${group.session_name}” from ${group.saved_on}, ` +
      `marked ${SESSION_STATUSES[group.session_status].toLowerCase()} (matched on phone number or email). Check before calling or submitting again.`);
  });
}

async function checkSeen() {
  seenElsewhere = [];
  if (!workspaceInfo.enabled || !baseResult || baseResult.hiring_mode !== "experienced") return;
  try {
    seenElsewhere = await workspaceCall("POST", "/seen", { result: baseResult, exclude_session: currentSession ? currentSession.id : null });
    if (seenElsewhere.length) render();
  } catch { /* a convenience only: the evaluation is unaffected */ }
}

function afterScreening() {
  currentSession = null;
  submission = null;
  renderSubmission();
  renderSessionBar();
  checkSeen();
}

function leaveSession() {
  currentSession = null;
  seenElsewhere = [];
  submission = null;
  renderSubmission();
}

function renderSessionBar() {
  const bar = $("session-bar");
  const show = workspaceInfo.enabled && lastResult && lastResult.hiring_mode === "experienced";
  bar.hidden = !show;
  if (!show) return;
  if (!currentSession) {
    const name = el("input", { type: "text", maxlength: "120", "aria-label": "Name for this session" });
    name.value = jobTitle();
    const save = el("button", { type: "button", class: "small" }, "Save session");
    const status = el("span", { class: "hint", role: "status" });
    const run = async () => {
      if (!name.value.trim()) { status.textContent = "Give it a name."; return; }
      save.disabled = true;
      try {
        const form = Object.fromEntries(Object.entries(FORM_BOXES).map(([key, id]) => [key, $(id).value]));
        const saved = await workspaceCall("POST", "/sessions", { name: name.value.trim(), job_description: $("job-description").value,
          form, result: baseResult, clarifications, submission: storedSubmission() });
        currentSession = { id: saved.id, name: saved.name, status: saved.status };
        savedAt = clockTime();
        renderSessionBar();
        checkSeen();
      } catch (error) { status.textContent = error.message; save.disabled = false; }
    };
    save.addEventListener("click", run);
    name.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); run(); } });
    bar.replaceChildren(el("span", {}, el("strong", {}, "Not saved. "), "This evaluation is gone when you close or reload the page."), name, save, status);
    return;
  }
  const status = el("select", { "aria-label": "Session status" },
    ...Object.entries(SESSION_STATUSES).map(([value, label]) => el("option", { value }, label)));
  status.value = currentSession.status;
  status.addEventListener("change", async () => {
    try {
      await workspaceCall("PATCH", `/sessions/${currentSession.id}`, { status: status.value });
      currentSession.status = status.value;
      savedAt = clockTime();
      renderSessionBar();
    } catch (error) { status.value = currentSession.status; }
  });
  bar.replaceChildren(el("span", {}, el("strong", {}, "Saved on this computer: "), currentSession.name), status,
    el("span", { class: "hint", id: "session-saved", role: "status" }, savedAt ? `Saved ${savedAt}. Call notes and the submission save as you go.` : ""));
}

// Called whenever call notes or the submission change. Saves quietly if this evaluation has been saved before.
function sessionChanged() {
  if (!currentSession) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    const note = $("session-saved");
    try {
      const stored = storedSubmission();
      await workspaceCall("PATCH", `/sessions/${currentSession.id}`,
        stored ? { clarifications, submission: stored } : { clarifications, clear_submission: true });
      savedAt = clockTime();
      if (note) note.textContent = `Saved ${savedAt}. Call notes and the submission save as you go.`;
    } catch (error) {
      if (note) note.textContent = `Not saved: ${error.message}`;
    }
  }, 500);
}

async function openSession(id) {
  const session = await workspaceCall("GET", `/sessions/${id}`);
  if (!experienced.checked) experienced.click();
  $("job-description").value = session.job_description;
  for (const [key, boxId] of Object.entries(FORM_BOXES)) $(boxId).value = session.form[key] || "";
  for (const boxId of Object.values(FORM_BOXES)) { const line = $("src-" + boxId); if (line) line.hidden = true; }
  fileInput.value = "";
  showFileList();
  startResult(session.result, session.clarifications);
  if (Object.keys(session.clarifications).length) {
    lastResult = await postJson("/api/clarifications/apply", { result: session.result, clarifications: session.clarifications });
  }
  currentSession = { id: session.id, name: session.name, status: session.status };
  savedAt = "";
  submission = session.submission ? { ...session.submission, excluded: new Set(session.submission.excluded || []) } : null;
  render();
  renderSubmission();
  checkSeen();
  $("sessions-dialog").close();
  $("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function showSessions() {
  const dialog = $("sessions-dialog");
  const close = el("button", { type: "button", class: "secondary small", style: "margin: 0" }, "Close");
  close.addEventListener("click", () => dialog.close());
  const head = el("div", { class: "sheet-head" }, el("div", {}, el("h2", { id: "sessions-title" }, "Saved sessions"),
    el("div", { class: "reason" }, `Kept in a file on this computer (${workspaceInfo.location}). Resume files are not kept: only the details shown on screen, your call notes and your submissions.`)), close);
  const body = el("div", { class: "sheet-body" }, el("p", { class: "hint" }, "Loading…"));
  dialog.replaceChildren(head, body);
  if (!dialog.open) dialog.showModal();
  let sessions;
  try { sessions = await workspaceCall("GET", "/sessions"); } catch (error) { body.replaceChildren(el("p", { class: "error" }, error.message)); return; }
  if (!sessions.length) {
    body.replaceChildren(el("p", {}, el("strong", {}, "Nothing saved yet.")),
      el("p", { class: "reason" }, "Evaluate resumes with “Hiring experienced candidates” ticked, then press “Save session” above the results. Each job you are working on can be its own session."));
    return;
  }
  const when = (iso) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const rows = sessions.map((session) => {
    const open = el("button", { type: "button", class: "linkish" }, session.name);
    open.addEventListener("click", async () => {
      try { await openSession(session.id); } catch (error) { body.prepend(el("p", { class: "error" }, error.message)); }
    });
    const remove = el("button", { type: "button", class: "icon-button", "aria-label": `Delete ${session.name}` }, "Delete");
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Delete “${session.name}” and everything recorded in it? This can't be undone.`)) return;
      try {
        await workspaceCall("DELETE", `/sessions/${session.id}`);
        if (currentSession && currentSession.id === session.id) { currentSession = null; renderSessionBar(); }
        showSessions();
      } catch (error) { body.prepend(el("p", { class: "error" }, error.message)); }
    });
    return el("tr", {}, el("td", {}, open, currentSession && currentSession.id === session.id ? el("span", { class: "hint" }, " (open now)") : null),
      el("td", {}, SESSION_STATUSES[session.status]), el("td", {}, String(session.candidates)),
      el("td", {}, session.with_call_notes ? String(session.with_call_notes) : "–"),
      el("td", {}, session.has_submission ? "Drafted" : "–"), el("td", {}, when(session.updated_at)), el("td", {}, remove));
  });
  body.replaceChildren(el("div", { class: "table-wrap" }, el("table", { class: "sessions-table" },
    el("thead", {}, el("tr", {}, ...["Session", "Status", "Candidates", "Call notes", "Submission", "Last changed", ""].map((text) => el("th", {}, text)))),
    el("tbody", {}, ...rows))));
}

$("sessions-open").addEventListener("click", showSessions);

(async function startWorkspace() {
  try {
    workspaceInfo = await (await fetch("/api/workspace")).json();
  } catch { workspaceInfo = { enabled: false, note: "" }; }
  $("sessions-open").hidden = !workspaceInfo.enabled;
  if (lastResult) renderSessionBar();
}());
