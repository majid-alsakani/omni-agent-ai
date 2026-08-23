# Data Analysis Lab Validation

## مصدر بيانات الاختبار

استُخدمت مجموعة Iris الرسمية من UCI. تؤكد وثيقة UCI أنها مجموعة tabular تحتوي 150 حالة و4 ميزات رقمية وفئة هدف واحدة، ولا تحتوي على قيم ناقصة. المصدر: https://archive.ics.uci.edu/dataset/53/iris

## اختبار API الحي

أُرسل ملف `tests/fixtures/uci_iris.csv` إلى `POST /analyze-data`. أعاد النظام:

- الوضع: `data-analysis-multi-agent`.
- البنية: 150 صفاً و5 أعمدة بعد إضافة رأس CSV واضح.
- أقوى علاقة: `petal_length` و`petal_width` بمعامل ارتباط `0.9628`.
- جودة البيانات: `99/100` وحالة `ممتازة`.
- وكلاء مكتملون: Data Profiling Agent وInsight Agent وData Quality Agent.

## فحص الواجهة

تم فتح Command Center في المتصفح. ظهر رابط مختبر تحليل البيانات في التنقل، ومنطقة رفع CSV، وزر التحليل، وحالة الخصوصية المحلية، دون إخفاء لوحة المهام أو تنسيق الوكلاء أو الذاكرة.
