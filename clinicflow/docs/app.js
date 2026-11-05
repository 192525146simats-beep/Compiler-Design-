// >>> EDIT THIS after you deploy on Streamlit Community Cloud <<<
const STREAMLIT_URL = "https://YOUR-APP-NAME.streamlit.app";

const R = document.documentElement, $ = (id) => document.getElementById(id), live = $("live");
const say = (t) => { live.textContent = ""; setTimeout(() => (live.textContent = t), 40); };

/* ---------- navigation ---------- */
const titles = { cc: "Hospital Command Center", pt: "Patient Workflow", ps: "Protocol Studio", fw: "Workflow Map", lc: "Live Compiler" };
const btns = [...document.querySelectorAll("#nav button")];
btns.forEach((b) => (b.onclick = () => {
  btns.forEach((x) => x.removeAttribute("aria-current"));
  b.setAttribute("aria-current", "page");
  document.querySelectorAll("[data-s]").forEach((s) => (s.hidden = s.dataset.s !== b.dataset.p));
  $("ttl").textContent = titles[b.dataset.p];
  $("main").focus();
  say(titles[b.dataset.p] + " page");
}));

/* ---------- accessibility ---------- */
let fs = 100;
const tog = (id, attr, msg) => ($(id).onclick = (e) => {
  const on = R.dataset[attr] !== "1";
  R.dataset[attr] = on ? "1" : "0";
  e.currentTarget.setAttribute("aria-pressed", on);
  say(msg + (on ? " on" : " off"));
});
tog("b-hc", "hc", "High contrast"); tog("b-dys", "dys", "Dyslexia font"); tog("b-calm", "calm", "Reduced motion");
$("b-plus").onclick = () => { fs = Math.min(160, fs + 10); R.style.setProperty("--fs", fs + "%"); say("Text size " + fs + " percent"); };
$("b-minus").onclick = () => { fs = Math.max(80, fs - 10); R.style.setProperty("--fs", fs + "%"); say("Text size " + fs + " percent"); };

let reading = false;
$("b-read").onclick = (e) => {
  if (!("speechSynthesis" in window)) return say("Read aloud is not supported in this browser");
  if (reading) { speechSynthesis.cancel(); reading = false; e.currentTarget.setAttribute("aria-pressed", "false"); return; }
  const vis = [...document.querySelectorAll("[data-s]")].find((s) => !s.hidden);
  const u = new SpeechSynthesisUtterance(vis.innerText);
  u.onend = () => { reading = false; $("b-read").setAttribute("aria-pressed", "false"); };
  speechSynthesis.speak(u);
  reading = true;
  e.currentTarget.setAttribute("aria-pressed", "true");
};

/* ---------- workflow map ---------- */
const W = [
  ["Capture", "Source input", "Vitals from monitors, lab feeds, EHR fields and clinician-written protocols arrive as raw text and data.", "The compiler’s input: source text."],
  ["Understand", "Module 1 · Lexer + Parser", "“If BP is above 140 then order an ECG” is split into tokens and checked against a grammar. Malformed rules are caught early, all at once.", "Lexical and syntax analysis."],
  ["Verify", "Module 2 · Semantic analysis", "Units, plausible vital ranges, drug maximum doses and data types are checked. A 9000 mg Paracetamol dose is rejected before it reaches anyone.", "Semantic analysis and symbol table."],
  ["Represent", "Module 2 · Intermediate code", "The protocol becomes neutral three-address steps, independent of any one hospital system.", "Three-address code generation."],
  ["Optimize", "Module 3 · Optimizer", "Duplicate ECGs removed, impossible branches dropped, constants folded: 45 steps become 7. Fewer tasks for staff.", "Folding, propagation, dead code removal."],
  ["Generate", "Module 3 · Code generation", "The same program is emitted as FHIR-style orders, nurse tasks, pharmacy queue items and dashboard alerts.", "Target code generation."],
  ["Run & learn", "Runtime + audit", "Clinician approves, actions execute, every step is logged. Protocol versions are tested before release.", "Execution and verification."],
];
const fl = $("flow"), det = $("det");
function show(i) {
  const w = W[i];
  det.innerHTML = "<h3>Stage " + (i + 1) + ": " + w[0] + "</h3><p><span class=\"tag\">HOSPITAL</span>" + w[2] +
    "</p><p><span class=\"tag\">COMPILER</span>" + w[3] + " (" + w[1] + ")</p>";
}
W.forEach((w, i) => {
  const b = document.createElement("button");
  b.setAttribute("aria-pressed", i === 0);
  b.innerHTML = "<small>STAGE " + (i + 1) + "</small><b>" + w[0] + "</b><span class=\"mut\">" + w[1] + "</span>";
  b.onclick = () => { [...fl.children].forEach((x) => x.setAttribute("aria-pressed", "false")); b.setAttribute("aria-pressed", "true"); show(i); };
  fl.appendChild(b);
});
show(0);

/* ---------- mini lexer for Protocol Studio ---------- */
const RU = [["C", /^\/\/[^\n]*/], ["N", /^\d+(\.\d+)?/], ["S", /^"[^"\n]*"/], ["I", /^[A-Za-z_]\w*/],
  ["O", /^(==|!=|<=|>=|[<>+\-*/=])/], ["P", /^[{}();,]/], ["W", /^\s+/]];
function lex(s) {
  let n = 0, e = 0;
  while (s.length) {
    let hit = false;
    for (const [t, re] of RU) {
      const m = s.match(re);
      if (m) { hit = true; if (t !== "W" && t !== "C") n++; s = s.slice(m[0].length); break; }
    }
    if (!hit) { e++; s = s.slice(1); }
  }
  return [n, e];
}
function upd() {
  const [n, e] = lex($("src").value), s = $("s1");
  s.className = "st " + (e ? "err" : "ok");
  s.textContent = e ? "✖ Syntax check: " + e + " invalid character(s)" : "✔ Syntax check";
  $("tokinfo").textContent = n + " tokens read by the lexer";
}
$("src").addEventListener("input", upd);
upd();

/* ---------- live compiler (Streamlit embed, loaded on first open) ---------- */
$("open-app").href = STREAMLIT_URL;
document.querySelector('[data-p="lc"]').addEventListener("click", () => {
  const f = $("app-frame");
  if (!f.src) f.src = STREAMLIT_URL + "/?embed=true";
}, { once: true });

/* ---------- intro animation ---------- */
(function () {
  const o = $("intro"), li = [...o.querySelectorAll("li")];
  let timers = [];
  const reduce = () => matchMedia("(prefers-reduced-motion:reduce)").matches || R.dataset.calm === "1";
  function end() {
    timers.forEach(clearTimeout);
    o.classList.add("out");
    setTimeout(() => { o.hidden = true; $("main").focus(); }, 700);
    try { sessionStorage.setItem("cf-intro", "1"); } catch (e) {}
  }
  function play() {
    if (reduce()) { o.hidden = true; return; }
    timers = [];
    o.hidden = false;
    o.classList.remove("out");
    li.forEach((l) => l.classList.remove("show", "done"));
    o.querySelectorAll("svg path,.pbar span").forEach((e) => { e.style.animation = "none"; void e.offsetHeight; e.style.animation = ""; });
    $("skip").focus();
    li.forEach((l, i) => {
      timers.push(setTimeout(() => l.classList.add("show"), 700 + i * 650));
      timers.push(setTimeout(() => l.classList.add("done"), 1150 + i * 650));
    });
    timers.push(setTimeout(end, 4300));
  }
  $("skip").onclick = end;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !o.hidden) end(); });
  $("b-replay").onclick = play;
  let seen = false;
  try { seen = sessionStorage.getItem("cf-intro") === "1"; } catch (e) {}
  seen ? (o.hidden = true) : play();
})();
