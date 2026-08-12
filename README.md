# 💎 Omni-Agent AI v3.0

<p align="center">
  <img src="artifacts/omni_logo.png" width="220" alt="Omni-Agent Logo">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Autonomous%20Multi--Agent-16a34a?style=for-the-badge" alt="Multi-Agent">
  <img src="https://img.shields.io/badge/Orchestration-LangGraph-7c3aed?style=for-the-badge" alt="LangGraph">
  <img src="https://img.shields.io/badge/Memory-Vector%20DB%20Ready-0284c7?style=for-the-badge" alt="Vector Memory">
  <img src="https://img.shields.io/badge/Tests-11%20passed-0f766e?style=for-the-badge" alt="Tests passed">
</p>

---

## 🎨 The Multi-Agent Evolution & Sovereign Memory

<p align="center">
  <img src="artifacts/multi_agent_dashboard.png" width="850" alt="Omni-Agent Multi-Agent Dashboard">
  <br>
  <i>Conceptual Dashboard: Multi-Agent Orchestration, Sovereign Semantic Memory (pgvector), and Real-time Task Decomposition.</i>
</p>

---

**Omni-Agent AI** هو نظام متطور لوكلاء الذكاء الاصطناعي المستقلين، يعتمد على بنية **التخطيط الذاتي متعدد الوكلاء (Multi-Agent Planning)**. النسخة 3.0 تنقل المشروع من مجرد وكيل واحد إلى "أوركسترا" من الوكلاء المتخصصين الذين يعملون بتناغم لحل المهام المعقدة، مع دعم كامل لقواعد البيانات المتجهية لضمان ذاكرة سيادية دائمة ودقيقة.

## 🌟 الميزات المتقدمة (نسخة 3.0)

| الميزة | الوصف التقني | الفائدة |
| --- | --- | --- |
| **Multi-Agent Orchestrator** | تنسيق مهام بين وكلاء (Researcher, Analyst, Risk Manager) عبر LangGraph | حل المهام المعقدة التي تتطلب بحثاً وتحليلاً ومراجعة مخاطر متوازية |
| **Auto-Planning Mode** | اكتشاف تلقائي لصعوبة المهمة والتحويل بين المسار الفردي والمتعدد | توفير الموارد للمهام البسيطة واستخدام القوة الكاملة للمهام المعقدة |
| **Vector Semantic Memory** | محرك ذاكرة متجهي يدعم pgvector و Local Hashed Vectors | استرجاع فائق السرعة والدقة للحقائق والتفضيلات الشخصية |
| **Self-Correction Loop** | حلقة مراجعة ونقد ذاتي (Reflexion) قبل تسليم النتيجة النهائية | ضمان أعلى مستويات الدقة وتقليل الهلوسة البرمجية |
| **Production Ready** | دعم كامل لـ Docker، PostgreSQL، وواجهة API متطورة | جاهزية تامة للنشر في بيئات الإنتاج السحابية |

---

## 🏗️ Architecture: The Brain & The Vault

<p align="center">
  <img src="artifacts/multi_agent_architecture.png" width="700" alt="Omni-Agent Multi-Agent Architecture">
</p>

يعتمد النظام على حلقة **PRAR (Perception, Reasoning, Action, Reflection)** المطورة:
1. **Perception:** استدعاء السياق من الذاكرة العرضية (JSON) والذاكرة الدلالية (Vector DB).
2. **Reasoning:** المنسق (Orchestrator) يحلل الهدف ويوزع المهام على الوكلاء المتخصصين.
3. **Action:** تنفيذ متوازي للمهام مع استخدام الأدوات والبيانات.
4. **Reflection:** مراجعة الاتساق (Consistency Review) ودمج النتائج (Synthesis) قبل التحديث النهائي للذاكرة.

---

## 🚀 التشغيل السريع

### 1. المتطلبات الأساسية
```bash
pip install -r backend/requirements.txt
# اختيارياً للذاكرة المتجهية الخارجية:
pip install -r backend/requirements-vector.txt
```

### 2. تشغيل الاختبارات الشاملة (11 اختباراً)
```bash
pytest -v
```

### 3. تشغيل النظام
```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. تجربة مهمة معقدة (Multi-Agent)
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "حلل مخاطر السوق ومقارنة البدائل الاستثمارية مع خطة بحث شاملة",
    "mode": "auto"
  }'
```

---

## 📂 هيكلية المشروع المحدثة
*   `backend/multi_agent.py`: محرك التنسيق بين الوكلاء المتخصصين.
*   `backend/vector_memory.py`: محولات الذاكرة المتجهية (Local/Postgres).
*   `backend/agent_engine.py`: محرك الوكيل الفردي السريع.
*   `backend/memory.py`: مدير الذاكرة الهجين (Hybrid Memory Manager).
*   `docs/vector-memory-setup.md`: دليل ربط قواعد البيانات الخارجية.

---

## 🛡️ الذاكرة السيادية (Sovereign Memory)
<p align="center">
  <img src="artifacts/sovereign_memory_icon.png" width="150" alt="Sovereign Memory Icon">
</p>

نحن نؤمن بأن معرفة المستخدم يجب أن تكون ملكاً له. يدعم Omni-Agent تخزين الذاكرة في قاعدة بياناتك الخاصة (Self-hosted pgvector)، مما يمنحك تحكماً كاملاً في بياناتك وسياقك التاريخي دون الاعتماد على خوادم خارجية مغلقة.

## الترخيص
MIT - حر للاستخدام والتطوير.
