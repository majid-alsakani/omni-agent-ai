const state = {
  health: null,
  tools: [],
  lastAnswer: "",
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function labelStatus(isOnline) {
  $("metric-status").textContent = isOnline ? "متصل" : "غير متصل";
  $("sidebar-health").textContent = isOnline ? "النظام يعمل" : "فشل الاتصال";
  $("environment-label").textContent = isOnline ? "الخدمة جاهزة" : "الخدمة غير متاحة";
  $("header-dot").classList.toggle("online", isOnline);
  document.querySelector(".pulse").classList.toggle("online", isOnline);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function refreshHealth() {
  try {
    const [health, tools] = await Promise.all([api("/health"), api("/tools")]);
    state.health = health;
    state.tools = tools.tools || [];
    labelStatus(true);
    $("metric-engines").textContent = (health.engines || []).length ? health.engines.join(" · ") : "محرك جاهز";
    $("metric-memory").textContent = Number(health.memory_records || 0).toLocaleString("ar");
    $("metric-vector").textContent = health.vector_store || "—";
    $("metric-tools").textContent = String(tools.count ?? state.tools.length ?? 0);
    $("tool-list").innerHTML = state.tools.map((tool) => `<span class="tool-tag">${escapeHtml(tool)}</span>`).join("") || "<span class='muted'>لا توجد أدوات مفعلة</span>";
  } catch (error) {
    labelStatus(false);
    $("metric-engines").textContent = "تحقق من الخادم";
    $("metric-vector").textContent = "غير متاح";
    $("tool-list").innerHTML = "<span class='muted'>تعذر تحميل الأدوات</span>";
  }
}

async function refreshMemory() {
  const userId = $("user-id").value.trim() || "command-center-user";
  const list = $("memory-list");
  list.innerHTML = "<p class='muted'>جاري استدعاء الذاكرة...</p>";
  try {
    const payload = await api(`/memory?user_id=${encodeURIComponent(userId)}`);
    if (!payload.items?.length) {
      list.innerHTML = "<p class='muted'>لا توجد ذاكرة لهذا المستخدم بعد. شغّل مهمة أو احفظ تفضيلاً.</p>";
      return;
    }
    list.innerHTML = payload.items.slice(0, 8).map((item) => {
      const type = item.kind === "semantic" ? "ذاكرة دلالية" : item.kind === "procedural" ? "ذاكرة إجرائية" : "حدث جلسة";
      const date = item.created_at ? new Date(item.created_at).toLocaleString("ar") : "الآن";
      return `<article class="memory-record">
        <div class="memory-meta"><span class="memory-kind">${escapeHtml(type)}</span><span>${escapeHtml(date)}</span></div>
        <p>${escapeHtml(item.content)}</p>
      </article>`;
    }).join("");
  } catch (error) {
    list.innerHTML = `<div class="error-box">تعذر تحميل الذاكرة: ${escapeHtml(error.message)}</div>`;
  }
}

function setGraph(result, mode) {
  document.querySelectorAll(".agent-node").forEach((node) => node.classList.remove("agent-active"));
  const agents = result.agents || result.agent_outputs?.map((item) => item.agent) || [];
  if (mode === "multi" || agents.length) {
    if (agents.some((value) => /research/i.test(value))) document.querySelector(".research").classList.add("agent-active");
    if (agents.some((value) => /analysis/i.test(value))) document.querySelector(".analyst").classList.add("agent-active");
    if (agents.some((value) => /risk/i.test(value))) document.querySelector(".risk").classList.add("agent-active");
  }
  const review = result.review || {};
  $("review-state").textContent = review.status === "approved" ? "تمت المراجعة والموافقة" : mode === "single" ? "تمت مراجعة المسار الفردي" : "تحتاج مراجعة";
}

function renderResult(payload) {
  const result = payload.data || {};
  state.lastAnswer = result.answer || "";
  $("copy-result").disabled = !state.lastAnswer;
  $("selected-mode-label").textContent = String(payload.mode || "auto").toUpperCase();
  setGraph(result, payload.mode);

  const traceItems = [
    ["نمط التشغيل", payload.mode || "auto"],
    ["الخطوات", result.steps_completed ?? result.agent_outputs?.length ?? "—"],
    ["المراجعة", result.review?.status || (result.review_attempts ? `${result.review_attempts} جولة` : "مكتملة")],
    ["الوكلاء", result.agents?.length ?? (payload.mode === "single" ? 1 : "—")],
  ];
  const trace = `<div class="trace-grid">${traceItems.map(([name, value]) => `<div class="trace-item"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>`;
  const agentOutputs = (result.agent_outputs || []).map((agent) => `<article class="agent-output"><strong>${escapeHtml(agent.agent)}</strong><p>${escapeHtml(agent.finding)}</p></article>`).join("");
  $("result-content").className = "";
  $("result-content").innerHTML = `${trace}${agentOutputs ? `<div class="agent-output-list">${agentOutputs}</div>` : ""}<div class="answer">${escapeHtml(result.answer || "لم تُرجع المهمة إجابة.")}</div>`;
}

async function runMission() {
  const prompt = $("prompt").value.trim();
  const mode = $("mode").value;
  const userId = $("user-id").value.trim() || "command-center-user";
  if (!prompt) {
    $("request-status").textContent = "اكتب وصفاً للمهمة أولاً.";
    $("request-status").className = "request-status warning";
    $("prompt").focus();
    return;
  }
  const button = $("run-mission");
  button.disabled = true;
  button.querySelector("span").textContent = "يجري التخطيط والتنفيذ...";
  $("request-status").textContent = "المنسق يراجع المهمة ويختار الوكلاء المناسبين.";
  $("request-status").className = "request-status";
  $("result-content").className = "loading-state";
  $("result-content").textContent = "جاري تشغيل محرك Omni-Agent...";
  try {
    const payload = await api("/ask", {
      method: "POST",
      body: JSON.stringify({ prompt, user_id: userId, session_id: "command-center-session", mode }),
    });
    renderResult(payload);
    $("request-status").textContent = payload.mode === "multi" ? "اكتملت المهمة متعددة الوكلاء بنجاح." : "اكتملت المهمة الفردية بنجاح.";
    $("request-status").className = "request-status success";
    await Promise.all([refreshHealth(), refreshMemory()]);
  } catch (error) {
    $("result-content").className = "error-box";
    $("result-content").textContent = `تعذر تشغيل المهمة: ${error.message}`;
    $("request-status").textContent = "تعذر إكمال المهمة.";
    $("request-status").className = "request-status warning";
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "تشغيل المهمة";
  }
}

$("run-mission").addEventListener("click", runMission);
$("refresh-memory").addEventListener("click", refreshMemory);
$("copy-result").addEventListener("click", async () => {
  if (!state.lastAnswer) return;
  try {
    await navigator.clipboard.writeText(state.lastAnswer);
    $("copy-result").textContent = "تم النسخ";
    setTimeout(() => { $("copy-result").textContent = "نسخ النتيجة"; }, 1600);
  } catch {
    $("copy-result").textContent = "تعذر النسخ";
  }
});
$("mode").addEventListener("change", () => { $("selected-mode-label").textContent = $("mode").value.toUpperCase(); });
document.querySelectorAll(".scenario").forEach((button) => button.addEventListener("click", () => {
  $("prompt").value = button.dataset.prompt || "";
  $("prompt").focus();
}));

refreshHealth();
refreshMemory();
