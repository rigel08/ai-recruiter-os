"use strict";

// The screening page. Loaded by index.html; workspace.js builds on the names defined here.

const $ = (id) => document.getElementById(id);
const LABELS = { shortlist: "Shortlist", maybe: "Maybe", not_a_fit: "Not a fit" };
const fileInput = $("resumes");
let lastResult = null;   // what is on screen: the screening result with any call answers applied
let baseResult = null;   // the result exactly as the screening returned it; call answers are applied to this
let clarifications = {}; // call answers and remarks, keyed by resume file name

function startResult(data, answers = {}) {
  baseResult = data;
  lastResult = data;
  clarifications = answers;
  activeFilter = "all";
  compared.clear();
}
let activeFilter = "all";

// ---------- Experienced-hire mode ----------

const FACTS = [
  ["total_experience", "Experience"], ["notice_period", "Notice"], ["current_ctc", "Current CTC"],
  ["expected_ctc", "Expected CTC"], ["current_location", "Location"], ["preferred_location", "Prefers"],
];
const FACT_NAMES = { phone: "Phone", total_experience: "Total experience", notice_period: "Notice period",
  current_ctc: "Current CTC", expected_ctc: "Expected CTC", current_location: "Current location",
  preferred_location: "Preferred location" };
const experienced = $("experienced");
// Storage can be blocked (private windows), so the page must work without it.
try { experienced.checked = localStorage.getItem("experienced") === "1"; } catch {}
const STEP_LABELS = { ready: "Looks ready", clarify: "Clarify first", check: "Check by hand",
  conflict: "Conflicts with a limit", low_fit: "Low skills fit" };
const STATUS_LABELS = { meets: "Meets", near: "Near match", does_not_meet: "Does not meet", unknown: "Unknown",
  needs_review: "Check by hand" };
const LEVEL_LABELS = { strong: "Strong", partial: "Partial", weak: "Weak", not_set: "Not scored" };
const compared = new Set();   // file names ticked for the side-by-side view

// The switch only changes the form. A result keeps the mode it was run in.
function syncMode() {
  const on = experienced.checked;
  $("requirements").hidden = !on;
  $("cgpa-field").hidden = on;
  $("must-label").textContent = on ? "Required skills" : "Must-have skills";
  if (!on) $("src-must-haves").hidden = true;
  $("submit").textContent = submitLabel();
}
const submitLabel = () => (experienced.checked ? "Evaluate resumes" : "Rank resumes");
experienced.addEventListener("change", () => {
  try { localStorage.setItem("experienced", experienced.checked ? "1" : "0"); } catch {}
  syncMode();
});

// ---------- Requirements read from the job description ----------

function sourceLine(id, nodes) {
  const line = $("src-" + id);
  line.replaceChildren(...nodes);
  line.hidden = nodes.length === 0;
}

// Explicit values go into the box. Anything only suggested stays out until the recruiter chooses it.
function offer(id, suggestion, shown) {
  const input = $(id);
  if (!suggestion) {
    input.value = "";
    sourceLine(id, ["Not stated in the job description."]);
    return;
  }
  const nodes = [];
  if (suggestion.basis === "explicit") {
    input.value = shown;
    nodes.push("From the job description: ", `“${suggestion.quote}”`);
  } else {
    input.value = "";
    const use = el("button", { type: "button", class: "linkish" }, "Use it");
    use.addEventListener("click", () => { input.value = shown; });
    nodes.push(el("strong", {}, "Suggestion only, not filled in: "), `${shown}, from “${suggestion.quote}” `, use);
  }
  if (suggestion.note) nodes.push(" " + suggestion.note);
  sourceLine(id, nodes);
}

async function readRequirements() {
  const status = $("read-status");
  const text = $("job-description").value;
  if (text.trim().length < 30) {
    status.textContent = "Paste the job description first.";
    return;
  }
  status.textContent = "Reading the job description…";
  try {
    const response = await fetch("/api/requirements", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_description: text }) });
    if (!response.ok) throw new Error();
    const found = await response.json();

    const required = found.required_skills.map((skill) => skill.name);
    $("must-haves").value = required.join(", ");
    sourceLine("must-haves", required.length
      ? ["From the job description: ", `“${found.required_skills[0].quote}”`]
      : ["No skills are stated as required in the job description. Type the ones the client insists on."]);

    const stated = found.preferred_skills.filter((skill) => skill.basis === "explicit").map((skill) => skill.name);
    const mentioned = found.preferred_skills.filter((skill) => skill.basis === "suggested").map((skill) => skill.name);
    $("preferred-skills").value = stated.join(", ");
    const nodes = stated.length ? ["Stated as preferred in the job description. "] : [];
    if (mentioned.length) {
      const add = el("button", { type: "button", class: "linkish" }, "Add them");
      add.addEventListener("click", () => {
        const current = $("preferred-skills").value.split(",").map((name) => name.trim()).filter(Boolean);
        $("preferred-skills").value = [...new Set([...current, ...mentioned])].join(", ");
      });
      nodes.push(el("strong", {}, "Only mentioned, not filled in: "), mentioned.join(", ") + ". ", add);
    }
    sourceLine("preferred-skills", nodes);

    offer("min-exp", found.min_experience_years, found.min_experience_years && String(found.min_experience_years.value));
    offer("max-exp", found.max_experience_years, found.max_experience_years && String(found.max_experience_years.value));
    offer("max-notice", found.max_notice_days, found.max_notice_days && String(found.max_notice_days.value));
    offer("max-ctc", found.max_ctc_lpa, found.max_ctc_lpa && String(found.max_ctc_lpa.value));
    offer("locations", found.locations, found.locations && found.locations.values.join(", "));

    const other = [...found.other, ...found.notes];
    $("req-other-list").replaceChildren(...other.map((item) => el("li", {}, item)));
    $("req-other").hidden = other.length === 0;
    status.textContent = "Filled in from the job description. Check every box: only what's in the boxes is used.";
  } catch {
    status.textContent = "The job description couldn't be read. Fill the boxes in by hand.";
  }
}

// ---------- Choosing files ----------

function showFileList() {
  const names = [...fileInput.files].map((file) => file.name);
  const list = $("file-list");
  list.hidden = names.length === 0;
  const shown = names.slice(0, 5).join(", ");
  list.textContent = `${names.length} file${names.length === 1 ? "" : "s"}: ${shown}` +
    (names.length > 5 ? ` and ${names.length - 5} more` : "");
}

fileInput.addEventListener("change", showFileList);
const drop = $("drop");
drop.addEventListener("dragover", (event) => { event.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (event) => {
  event.preventDefault();
  drop.classList.remove("over");
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    showFileList();
  }
});

$("sample").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/samples?kind=" + (experienced.checked ? "experienced" : "campus"));
    if (!response.ok) throw new Error();
    const sample = await response.json();
    $("job-description").value = sample.job_description;
    $("must-haves").value = sample.must_haves;
    $("min-cgpa").value = sample.min_cgpa === null ? "" : sample.min_cgpa.toFixed(1);
    const transfer = new DataTransfer();
    for (const resume of sample.resumes) {
      transfer.items.add(new File([resume.text], resume.file_name, { type: "text/plain" }));
    }
    fileInput.files = transfer.files;
    showFileList();
    if (experienced.checked) await readRequirements();
    form.requestSubmit();
  } catch {
    showError("The sample data couldn't be loaded. Please try again.");
  }
});

// ---------- Screening ----------

const form = $("screen-form");
const submit = $("submit");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = fileInput.files;
  const body = new FormData();
  body.append("job_description", $("job-description").value);
  body.append("must_haves", $("must-haves").value);
  if (experienced.checked) {
    // Only what is in the boxes is sent, so only that is checked.
    body.append("hiring_mode", "experienced");
    body.append("preferred_skills", $("preferred-skills").value);
    body.append("min_experience_years", $("min-exp").value);
    body.append("max_experience_years", $("max-exp").value);
    body.append("max_notice_days", $("max-notice").value);
    body.append("max_ctc_lpa", $("max-ctc").value);
    body.append("locations", $("locations").value);
  } else if ($("min-cgpa").value !== "") {
    body.append("min_cgpa", $("min-cgpa").value);
  }
  for (const file of files) body.append("resumes", file);

  $("error").hidden = true;
  submit.disabled = true;
  submit.textContent = `${experienced.checked ? "Evaluating" : "Ranking"} ${files.length} resume${files.length === 1 ? "" : "s"}…`;
  try {
    const response = await fetch("/api/screenings", { method: "POST", body });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(errorMessage(data));
    startResult(data);
    render();
    afterScreening();
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = submitLabel();
  }
});

function showError(message) {
  $("error").textContent = message || "Something went wrong. Please try again.";
  $("error").hidden = false;
}

function errorMessage(data) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const field = detail[0].loc ? detail[0].loc[detail[0].loc.length - 1] : "";
    if (field === "job_description") return "The job description needs to be between 30 and 20,000 characters.";
    if (field === "must_haves") return "The must-have list is too long. Keep it under 2,000 characters.";
    if (field === "min_cgpa") return "The minimum CGPA must be a number from 0 to 10.";
    if (field === "resumes") return "Choose at least one resume.";
    if (field === "min_experience_years" || field === "max_experience_years") return "Experience must be a number of years from 0 to 50.";
    if (field === "max_notice_days") return "The longest notice period must be a number of days from 0 to 180.";
    if (field === "max_ctc_lpa") return "The highest expected CTC must be a number of lakhs from 0.5 to 500.";
    if (field === "preferred_skills" || field === "locations") return "That list is too long. Shorten it.";
  }
  return "Something went wrong. Please try again.";
}

// ---------- Results ----------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  }
  return node;
}

const chips = (names) => el("div", { class: "chips" }, ...names.map((name) => el("span", { class: "chip" }, name)));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
// 7 -> "7.0", 8.25 -> "8.25": the same format the server uses in summaries.
const cgpaText = (value) => {
  const text = value.toFixed(2).replace(/0+$/, "");
  return text.endsWith(".") ? text + "0" : text;
};

function render() {
  const data = lastResult;
  const isExperienced = data.hiring_mode === "experienced";
  const groupOf = (c) => (isExperienced ? c.evaluation.next_step.key : c.decision);
  $("results-title").textContent = `${isExperienced ? "Evaluated" : "Ranked"} ${plural(data.ranked_count, "resume")}`;
  $("campus-wrap").hidden = isExperienced;
  $("exp-wrap").hidden = !isExperienced;

  const criteria = $("criteria");
  criteria.replaceChildren();
  if (isExperienced) {
    criteria.append(...requirementsSummary(data), ...duplicateNotes(data));
  } else {
    if (data.must_haves.length) criteria.append(el("strong", {}, "Must-haves"), chips(data.must_haves));
    if (data.other_skills.length) {
      criteria.append(el("strong", {}, "Other skills from the job description"), chips(data.other_skills));
    }
    if (data.min_cgpa !== null) criteria.append(el("p", { style: "margin: 0 0 12px" }, el("strong", {}, "CGPA cut-off: "), cgpaText(data.min_cgpa)));
  }

  const counts = isExperienced ? data.next_step_counts : data.decision_counts;
  const names = isExperienced ? STEP_LABELS : LABELS;
  const filters = [["all", `All (${data.ranked_count + data.needs_review_count})`],
    ...Object.keys(names).map((key) => [key, `${names[key]} (${counts[key]})`])];
  if (data.needs_review_count) filters.push(["review", `Need a manual look (${data.needs_review_count})`]);
  const tabs = $("tabs");
  tabs.replaceChildren(...filters.map(([key, label]) => {
    const tab = el("button", { type: "button", class: "tab", "aria-pressed": String(key === activeFilter) }, label);
    tab.addEventListener("click", () => { activeFilter = key; render(); });
    return tab;
  }));

  const ranked = data.candidates.filter((c) => c.status === "ranked");
  const visible = ranked.filter((c) => activeFilter === "all" || groupOf(c) === activeFilter);
  $(isExperienced ? "exp-rows" : "rows").replaceChildren(...visible.map(isExperienced ? experiencedRow : row));
  $("empty").hidden = visible.length > 0 || activeFilter === "review";

  const review = data.candidates.filter((c) => c.status === "needs_review");
  $("review-list").replaceChildren(...review.map((c) => el("li", {}, el("strong", {}, c.file_name), ": " + c.summary)));
  $("review").hidden = review.length === 0 || !(activeFilter === "all" || activeFilter === "review");

  const top = isExperienced ? "ready" : "shortlist";
  $("copy-emails").textContent = copyLabel();
  $("copy-emails").disabled = !ranked.some((c) => groupOf(c) === top && c.email);
  renderCompare();
  renderSessionBar();
  $("results").hidden = false;
}

const copyLabel = () => (lastResult && lastResult.hiring_mode === "experienced"
  ? "Copy “looks ready” emails" : "Copy shortlisted emails");

function row(c) {
  const must = el("td");
  for (const skill of c.must_haves_matched) must.append(el("span", { class: "tag has" }, "✓ " + skill));
  for (const skill of c.must_haves_missing) must.append(el("span", { class: "tag missing" }, "✗ " + skill));
  if (!lastResult.must_haves.length) must.append(el("span", { class: "hint" }, "None set"));

  const why = el("td", { class: "why" }, c.summary);
  for (const flag of c.flags) why.append(el("p", { class: "flag" }, flag));
  if (c.interview_questions.length) {
    why.append(el("details", {},
      el("summary", {}, "Suggested interview questions"),
      el("ol", {}, ...c.interview_questions.map((q) => el("li", {}, q)))));
  }

  return el("tr", {},
    el("td", { class: "rank" }, String(c.rank)),
    el("td", { class: "who" },
      el("strong", {}, c.name || c.file_name),
      c.email ? el("span", {}, c.email) : null,
      c.name ? el("span", {}, c.file_name) : null),
    el("td", {}, el("span", { class: `badge ${c.decision}` }, LABELS[c.decision])),
    el("td", { class: "score" },
      el("b", {}, String(c.score)), " / 100",
      el("div", { class: "bar" }, el("i", { style: `width: ${c.score}%` }))),
    el("td", { class: "cgpa" }, c.cgpa === null ? "–" : cgpaText(c.cgpa)),
    must,
    why);
}

// ---------- Experienced hiring: three separate views of each candidate ----------

function requirementsSummary(data) {
  const r = data.requirements;
  const range = r.min_experience_years !== null && r.max_experience_years !== null
    ? `${r.min_experience_years} to ${r.max_experience_years} years`
    : r.min_experience_years !== null ? `${r.min_experience_years} years or more`
      : r.max_experience_years !== null ? `up to ${r.max_experience_years} years` : "no limit";
  const limits = [
    ["Experience", range],
    ["Notice period", r.max_notice_days === null ? "no limit" : r.max_notice_days === 0 ? "immediate" : `${r.max_notice_days} days or less`],
    ["Expected CTC", r.max_ctc_lpa === null ? "no limit" : `up to ${r.max_ctc_lpa} LPA`],
    ["Location", r.locations.length ? r.locations.join(" or ") : "no limit"],
  ];
  const nodes = [];
  if (r.required_skills.length) nodes.push(el("strong", {}, "Required skills"), chips(r.required_skills));
  if (r.preferred_skills.length) nodes.push(el("strong", {}, "Preferred skills"), chips(r.preferred_skills));
  nodes.push(el("p", { class: "coverage" }, el("strong", {}, "Checked against: "),
    limits.map(([label, value]) => `${label}: ${value}`).join(" · ")));
  nodes.push(el("p", { class: "coverage" }, el("strong", {}, "How to read this: "),
    "skills, client limits and information are judged separately and never combined into one score. ",
    "“Unknown” means the resume doesn't say, which is a question for the call, not a failure. ",
    "Order: looks ready, clarify first, check by hand, conflicts with a limit, low skills fit. Nobody is removed."));
  if (data.ranked_count) {
    const found = [["notice_period", "notice period"], ["current_ctc", "current CTC"], ["expected_ctc", "expected CTC"],
      ["total_experience", "total experience"], ["current_location", "current location"], ["phone", "phone"]]
      .map(([key, label]) => `${label} ${data.fact_coverage[key]}`).join(", ");
    nodes.push(el("p", { class: "coverage" },
      el("strong", {}, `Stated on the resume, out of ${data.ranked_count}: `), found + ". ",
      el("span", { class: "hint" }, "Blanks aren't guessed.")));
  }
  return nodes;
}

const statusChip = (status) => el("span", { class: `st ${status}` }, STATUS_LABELS[status]);
const levelBadge = (skills) => el("span", { class: `badge level-${skills.level}` },
  LEVEL_LABELS[skills.level] + (skills.score === null ? "" : ` · ${skills.score}`));
const stepBadge = (step) => el("span", { class: `badge step-${step.key}` }, step.label);

function checkLine(check) {
  return el("div", { class: "check" }, statusChip(check.status), " ", el("strong", {}, check.label),
    el("span", { class: "hint" }, ` (asked: ${check.required})`),
    el("div", { class: "reason" }, check.reason));
}

function skillTags(skills) {
  const tags = el("div", { style: "margin-top: 6px" });
  for (const skill of skills.required_matched) tags.append(el("span", { class: "tag has" }, "✓ " + skill));
  for (const skill of skills.required_missing) tags.append(el("span", { class: "tag missing" }, "✗ " + skill));
  return tags;
}

function preferredText(skills) {
  const total = skills.preferred_matched.length + skills.preferred_missing.length;
  if (!total) return null;
  return `Preferred: ${skills.preferred_matched.length} of ${total}` +
    (skills.preferred_matched.length ? ` (${skills.preferred_matched.join(", ")})` : "");
}

function experiencedRow(c) {
  const e = c.evaluation;
  const pick = el("input", { type: "checkbox", "aria-label": `Compare ${c.name || c.file_name}`, title: "Tick to compare side by side" });
  pick.checked = compared.has(c.file_name);
  pick.addEventListener("change", () => {
    if (pick.checked) compared.add(c.file_name); else compared.delete(c.file_name);
    renderCompare();
  });

  const skills = el("td", { class: "dim" }, levelBadge(e.skills), skillTags(e.skills));
  if (preferredText(e.skills)) skills.append(el("div", { class: "reason", style: "margin-bottom: 8px" }, preferredText(e.skills)));
  if (e.skills.experience) skills.append(checkLine(e.skills.experience));
  const how = el("details", {}, el("summary", {}, "How this is worked out"), el("p", { class: "reason" }, e.skills.explanation));
  if (c.interview_questions.length) {
    how.append(el("p", { class: "reason" }, "Suggested interview questions:"),
      el("ol", {}, ...c.interview_questions.map((q) => el("li", {}, q))));
  }
  skills.append(how);

  const limits = el("td", { class: "dim" });
  if (e.constraints.checks.length) limits.append(...e.constraints.checks.map(checkLine));
  else limits.append(el("span", { class: "hint" }, "No client limits were set."));

  const info = infoCell(c);

  return el("tr", {},
    el("td", { class: "rank" }, String(c.rank), pick),
    el("td", { class: "who" },
      el("strong", {}, c.name || c.file_name),
      c.email ? el("span", {}, c.email) : null,
      c.resolved.phone.display ? el("span", {}, c.resolved.phone.display,
        c.resolved.phone.source === "resume" ? null : sourceTag(c.resolved.phone.source)) : null,
      c.name ? el("span", {}, c.file_name) : null),
    el("td", { class: "dim step" }, stepBadge(e.next_step), el("div", { class: "reason" }, e.next_step.reason)),
    skills, limits, info);
}

// ---------- Side by side ----------

const MAX_COMPARED = 4;

function renderCompare() {
  renderSelection();
  const chosen = lastResult && lastResult.hiring_mode === "experienced"
    ? lastResult.candidates.filter((c) => c.status === "ranked" && compared.has(c.file_name)) : [];
  const section = $("compare");
  section.hidden = chosen.length === 0;
  if (!chosen.length) return;
  const shown = chosen.slice(0, MAX_COMPARED);
  $("compare-title").textContent = `Side by side (${shown.length})`;
  const note = $("compare-note");
  note.hidden = chosen.length >= 2 && chosen.length <= MAX_COMPARED;
  note.textContent = chosen.length < 2 ? "Tick one more candidate to compare."
    : `Showing the first ${MAX_COMPARED} of ${chosen.length} ticked.`;

  // The value in use (which may come from a call), falling back to the resume's own words.
  const fact = (c, key) => (c.resolved && c.resolved[key].display)
    || (c.facts[key] ? c.facts[key].display : "Not stated");
  const withCheck = (text, check) => el("td", {}, text, check ? " " : null, check ? statusChip(check.status) : null,
    check ? el("div", { class: "reason" }, check.reason) : null);
  const limit = (c, key) => c.evaluation.constraints.checks.find((check) => check.requirement === key);
  const lines = [
    ["Next step", (c) => el("td", {}, stepBadge(c.evaluation.next_step), el("div", { class: "reason" }, c.evaluation.next_step.reason))],
    ["Skills fit", (c) => el("td", {}, levelBadge(c.evaluation.skills))],
    ["Required skills", (c) => el("td", {}, skillTags(c.evaluation.skills))],
    ["Preferred skills", (c) => el("td", {}, preferredText(c.evaluation.skills) || "None set")],
    ["Experience", (c) => withCheck(fact(c, "total_experience"), c.evaluation.skills.experience)],
    ["Notice period", (c) => withCheck(fact(c, "notice_period"), limit(c, "notice_period"))],
    ["Current CTC", (c) => el("td", {}, fact(c, "current_ctc"))],
    ["Expected CTC", (c) => withCheck(fact(c, "expected_ctc"), limit(c, "ctc"))],
    ["Location", (c) => withCheck(fact(c, "current_location") +
      (fact(c, "preferred_location") !== "Not stated" ? `; prefers ${fact(c, "preferred_location")}` : ""), limit(c, "location"))],
    ["Missing or unclear", (c) => el("td", {},
      [...c.evaluation.completeness.missing, ...c.evaluation.completeness.unclear].join(", ") || "Nothing")],
    ["Evidence", (c) => el("td", { class: "facts" }, factsCell(c).querySelector("details") || "No facts stated.")],
  ];
  $("compare-table").replaceChildren(
    el("thead", {}, el("tr", {}, el("th", {}, ""), ...shown.map((c) => el("th", { scope: "col" }, c.name || c.file_name)))),
    el("tbody", {}, ...lines.map(([label, cell]) => el("tr", {}, el("th", { scope: "row" }, label), ...shown.map(cell)))));
}

$("compare-clear").addEventListener("click", () => {
  compared.clear();
  render();
});

// "Notice period: not on the resume" -> "Notice period"; other reasons are kept in brackets.
function askText(items) {
  return items.map((item) => {
    const cut = item.indexOf(": ");
    const label = item.slice(0, cut), reason = item.slice(cut + 2);
    return reason === "not on the resume" ? label : `${label} (${reason})`;
  }).join(", ");
}

function factsCell(c) {
  const cell = el("td", { class: "facts" });
  const list = el("dl");
  const evidence = [];
  for (const [key, label] of FACTS) {
    const fact = c.facts[key];
    if (!fact) continue;
    const value = el("dd", fact.value === null ? { class: "unclear" } : {}, fact.display);
    if (fact.confirm) value.append(el("span", { class: "check" }, "check"));
    list.append(el("dt", {}, label), value);
  }
  for (const key of Object.keys(FACT_NAMES)) {
    const fact = c.facts[key];
    if (fact) {
      // The quote is the item's own text (not a child element), with real quotation marks, so it
      // survives copying and is read out by screen readers. The tool's own remark is kept apart.
      evidence.push(el("li", {}, el("strong", {}, FACT_NAMES[key] + ": "), `“${fact.quote}”`,
        fact.note ? el("span", { class: "note" }, "Note: " + fact.note) : null));
    }
  }
  if (list.children.length) cell.append(list);
  else cell.append(el("span", { class: "hint" }, "Nothing stated on the resume."));
  if (c.to_ask.length) cell.append(el("p", { class: "ask" }, el("strong", {}, "Ask on the call: "), askText(c.to_ask)));
  if (evidence.length) {
    cell.append(el("details", {}, el("summary", {}, "Where each value came from (exact resume text)"), el("ul", { class: "evidence" }, ...evidence)));
  }
  return cell;
}

// ---------- Exports ----------

$("copy-emails").addEventListener("click", async () => {
  const button = $("copy-emails");
  const isExperienced = lastResult.hiring_mode === "experienced";
  const emails = lastResult.candidates
    .filter((c) => c.status === "ranked" && c.email && (isExperienced ? c.evaluation.next_step.key === "ready" : c.decision === "shortlist"))
    .map((c) => c.email);
  try {
    await navigator.clipboard.writeText(emails.join(", "));
    button.textContent = `Copied ${plural(emails.length, "email")}`;
  } catch {
    button.textContent = "Couldn't copy. Use the CSV instead";
  }
  setTimeout(() => { button.textContent = copyLabel(); }, 2500);
});

// The server builds the file from the result on screen, so the page and the CSV can't drift apart.
$("download").addEventListener("click", async () => {
  const button = $("download");
  try {
    const response = await fetch("/api/exports/csv", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(lastResult) });
    if (!response.ok) throw new Error();
    const link = el("a", { href: URL.createObjectURL(await response.blob()), download: "shortlist.csv" });
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  } catch {
    button.textContent = "Couldn't build the CSV. Try again";
    setTimeout(() => { button.textContent = "Download CSV"; }, 2500);
  }
});

$("again").addEventListener("click", () => {
  fileInput.value = "";
  showFileList();
  $("results").hidden = true;
  lastResult = null;
  baseResult = null;
  clarifications = {};
  compared.clear();
  leaveSession();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

$("read-jd").addEventListener("click", readRequirements);
syncMode();

// A link ending in ?demo=1 runs the sample straight away, for demos.
if (new URLSearchParams(location.search).has("demo")) $("sample").click();
