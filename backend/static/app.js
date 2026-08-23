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
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
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

function renderDataResult(payload) {
  const data = payload.data || {};
  const overview = data.overview || {};
  const quality = data.quality || {};
  const insights = data.insights || {};
  state.lastAnswer = data.summary || "";
  $("copy-result").disabled = !state.lastAnswer;
  const topCorrelation = insights.top_correlations?.[0];
  const cards = [
    ["الصفوف", overview.rows ?? "—"],
    ["الأعمدة", overview.columns ?? "—"],
    ["درجة الجودة", `${quality.score ?? "—"}/100`],
    ["قيم ناقصة", `${quality.missing_rate ?? "—"}%`],
  ];
  const columns = (overview.column_names || []).slice(0, 18).map((column) => `<span>${escapeHtml(column)}</span>`).join("");
  const agents = (data.agents || []).map((agent) => `<article class="agent-output"><strong>${escapeHtml(agent.agent)}</strong><p>${escapeHtml(agent.finding)}</p></article>`).join("");
  const recommendations = (quality.recommendations || []).map((item) => `<p>${escapeHtml(item)}</p>`).join("");
  $("data-result").className = "data-result";
  $("data-result").innerHTML = `
    <div class="data-summary">${escapeHtml(data.summary || "اكتمل التحليل.")}</div>
    <div class="data-grid">${cards.map(([name, value]) => `<div class="data-card"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>
    <div class="data-columns">${columns}</div>
    ${topCorrelation ? `<div class="insight-list"><p>أقوى ارتباط: ${escapeHtml(topCorrelation.left)} ↔ ${escapeHtml(topCorrelation.right)} (${escapeHtml(topCorrelation.correlation)})</p></div>` : ""}
    <div class="insight-list">${recommendations}</div>
    ${agents ? `<div class="agent-output-list">${agents}</div>` : ""}`;
  $("result-content").className = "";
  $("result-content").innerHTML = `<div class="trace-grid"><div class="trace-item"><span>المسار</span><strong>تحليل بيانات</strong></div><div class="trace-item"><span>الوكلاء</span><strong>${escapeHtml(data.agents?.length ?? 0)}</strong></div><div class="trace-item"><span>الخصوصية</span><strong>محلي</strong></div></div><div class="answer">${escapeHtml(data.summary || "")}</div>`;
  $("selected-mode-label").textContent = "DATA";
}

async function analyzeData() {
  const input = $("data-file");
  const file = input.files?.[0];
  const userId = $("user-id").value.trim() || "command-center-user";
  if (!file) {
    $("data-request-status").textContent = "اختر ملف CSV أولاً.";
    $("data-request-status").className = "request-status warning";
    return;
  }
  const button = $("analyze-data");
  button.disabled = true;
  button.querySelector("span").textContent = "يجري التحليل...";
  $("data-request-status").textContent = "وكلاء الاستكشاف والتحليل والجودة يراجعون الملف محلياً.";
  $("data-request-status").className = "request-status";
  $("data-result").className = "data-result loading-state";
  $("data-result").textContent = "جاري قراءة CSV وإنشاء المخرجات...";
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", userId);
    formData.append("session_id", "command-center-data-session");
    const payload = await api("/analyze-data", { method: "POST", body: formData });
    renderDataResult(payload);
    $("data-request-status").textContent = "اكتمل تحليل البيانات عبر ثلاثة وكلاء بنجاح.";
    $("data-request-status").className = "request-status success";
    await Promise.all([refreshHealth(), refreshMemory()]);
  } catch (error) {
    $("data-result").className = "data-result error-box";
    $("data-result").textContent = `تعذر تحليل الملف: ${error.message}`;
    $("data-request-status").textContent = "تعذر إكمال التحليل.";
    $("data-request-status").className = "request-status warning";
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "حلل البيانات";
  }
}

function renderTwinResult(payload) {
  const twin = payload.data || {};
  const assessment = twin.assessment || {};
  const evidence = twin.evidence || {};
  const sales = evidence.sales || {};
  state.lastAnswer = assessment.recommendation || "";
  $("copy-result").disabled = !state.lastAnswer;
  const cards = [
    ["الثقة", `${assessment.confidence_score ?? "—"}/100`],
    ["السوابق", twin.precedents?.length ?? 0],
    ["جودة الدليل", `${evidence.quality_score ?? "—"}/100`],
    ["الحالة", twin.status || "—"],
  ];
  const plan = (twin.plan || []).map((step) => `<article class="twin-step"><strong>${escapeHtml(step.agent)}</strong><span>${escapeHtml(step.action)}</span><small>${escapeHtml(step.status)}</small></article>`).join("");
  const risks = (assessment.gaps_and_risks || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const precedents = (twin.precedents || []).map((item) => `<p>${escapeHtml(item.content)}</p>`).join("");
  const salesLine = sales.detected ? `<p>صافي مبيعات: ${escapeHtml(sales.net_revenue)} · الطلبات المكتملة: ${escapeHtml(sales.completed_orders)} · قيمة الإلغاءات: ${escapeHtml(sales.cancellation_value)}</p>` : "";
  $("twin-result").className = "twin-result";
  $("twin-result").innerHTML = `
    <div class="data-grid">${cards.map(([name, value]) => `<div class="data-card"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>
    <div class="twin-summary"><strong>التوصية غير المنفذة:</strong> ${escapeHtml(assessment.recommendation || "لا توجد توصية")}${salesLine}</div>
    <h3>خطة التحقق</h3><div class="twin-plan">${plan}</div>
    <h3>فجوات الدليل والمخاطر</h3><ul class="twin-risk-list">${risks}</ul>
    ${precedents ? `<h3>سوابق مسترجعة</h3><div class="insight-list">${precedents}</div>` : ""}
    <p class="twin-approval-note">معرّف المسودة: ${escapeHtml(twin.id)} — لا تُخزن كمعرفة دلالية إلا عبر مسار الاعتماد البشري.</p>`;
  $("result-content").className = "";
  $("result-content").innerHTML = `<div class="trace-grid"><div class="trace-item"><span>المسار</span><strong>توأم استراتيجي</strong></div><div class="trace-item"><span>الثقة</span><strong>${escapeHtml(assessment.confidence_score ?? "—")}/100</strong></div><div class="trace-item"><span>المراجعة</span><strong>مطلوبة</strong></div></div><div class="answer">${escapeHtml(assessment.recommendation || "")}</div>`;
  $("selected-mode-label").textContent = "TWIN";
}

async function runStrategicTwin() {
  const file = $("twin-file").files?.[0];
  const objective = $("twin-objective").value.trim();
  const userId = $("user-id").value.trim() || "command-center-user";
  if (!file || !objective) {
    $("twin-request-status").textContent = "اكتب هدف القرار واختر ملف CSV كدليل.";
    $("twin-request-status").className = "request-status warning";
    return;
  }
  const button = $("run-twin");
  button.disabled = true;
  button.querySelector("span").textContent = "يجري بناء المسودة...";
  $("twin-request-status").textContent = "يستدعي التوأم السوابق، يحلل الدليل، ويجهز مسودة للمراجعة البشرية.";
  $("twin-request-status").className = "request-status";
  $("twin-result").className = "twin-result loading-state";
  $("twin-result").textContent = "جاري تشغيل دورة التوأم الاستراتيجي...";
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("objective", objective);
    formData.append("user_id", userId);
    formData.append("session_id", "command-center-twin-session");
    const payload = await api("/strategic-twin/analyze-data", { method: "POST", body: formData });
    renderTwinResult(payload);
    $("twin-request-status").textContent = "تم إنشاء مسودة قرار. راجعها واعتمدها فقط عبر مسار موافقة بشري صريح.";
    $("twin-request-status").className = "request-status success";
    await Promise.all([refreshHealth(), refreshMemory()]);
  } catch (error) {
    $("twin-result").className = "twin-result error-box";
    $("twin-result").textContent = `تعذر إنشاء مسودة القرار: ${error.message}`;
    $("twin-request-status").textContent = "تعذر إكمال دورة التوأم.";
    $("twin-request-status").className = "request-status warning";
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "إنشاء مسودة قرار";
  }
}

$("run-mission").addEventListener("click", runMission);
$("refresh-memory").addEventListener("click", refreshMemory);
$("analyze-data").addEventListener("click", analyzeData);
$("data-file").addEventListener("change", () => {
  const file = $("data-file").files?.[0];
  $("selected-file").textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : "لم يتم اختيار ملف";
});
$("run-twin").addEventListener("click", runStrategicTwin);
$("twin-file").addEventListener("change", () => {
  const file = $("twin-file").files?.[0];
  $("selected-twin-file").textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : "لم يتم اختيار ملف";
});
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
