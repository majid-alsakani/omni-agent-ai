"""Deterministic multi-agent CSV analysis for Omni-Agent.

The first version performs local, explainable analysis. It does not transmit the
uploaded file to any external provider and only stores a compact aggregate summary
in episodic memory.
"""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd

from .memory import MemoryStore


MAX_FILE_BYTES = int(os.getenv("OMNI_MAX_UPLOAD_MB", "64")) * 1024 * 1024
MAX_ROWS = int(os.getenv("OMNI_MAX_UPLOAD_ROWS", "1000000"))
MAX_COLUMNS = 100


def _native(value: Any) -> Any:
    """Convert pandas and NumPy scalars into JSON-safe native values."""
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, 4)
    if hasattr(value, "item"):
        return _native(value.item())
    return value


def _percentage(value: float) -> float:
    return round(float(value) * 100, 2)


class DataAnalysisEngine:
    """Run a transparent analysis workflow with three deterministic specialists."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def run(
        self,
        content: bytes,
        *,
        source_name: str,
        user_id: str = "default_user",
        session_id: str = "default_session",
    ) -> dict[str, Any]:
        dataframe = self._read_csv(content, source_name)
        overview = self._profile_agent(dataframe)
        insights = self._insight_agent(dataframe, overview)
        sales = self._sales_agent(dataframe)
        quality = self._quality_agent(dataframe, overview)
        agents = self._agent_outputs(overview, insights, quality, sales)
        summary = self._synthesize(source_name, overview, insights, quality, sales)

        self.memory.add(
            (
                f"تحليل بيانات: المصدر {Path(source_name).name}; "
                f"{overview['rows']} صفاً و{overview['columns']} عموداً؛ "
                f"درجة الجودة {quality['score']}/100؛ "
                f"أبرز نتيجة: {insights['headline']}"
                + (f"؛ صافي مبيعات مقدر {sales['net_revenue']:.2f}" if sales["detected"] else "")
            ),
            kind="episodic",
            user_id=user_id,
            session_id=session_id,
            importance=0.65,
            metadata={
                "mode": "data_analysis",
                "source_name": Path(source_name).name,
                "rows": overview["rows"],
                "columns": overview["columns"],
                "quality_score": quality["score"],
                "sales_detected": sales["detected"],
                "net_revenue": sales.get("net_revenue"),
            },
        )

        return {
            "mode": "data-analysis-multi-agent",
            "source": {"name": Path(source_name).name, "stored": False},
            "overview": overview,
            "insights": insights,
            "sales": sales,
            "quality": quality,
            "agents": agents,
            "summary": summary,
            "privacy": "تم التحليل محلياً ولم يُحفظ محتوى الملف؛ حُفظ ملخص مجمع فقط في ذاكرة الجلسة.",
        }

    def _read_csv(self, content: bytes, source_name: str) -> pd.DataFrame:
        if not content:
            raise ValueError("ملف CSV فارغ")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError(f"حجم الملف يتجاوز الحد المسموح ({MAX_FILE_BYTES // (1024 * 1024)} MB)")
        if Path(source_name).suffix.casefold() != ".csv":
            raise ValueError("النسخة الحالية تقبل ملفات CSV فقط")
        if b"\x00" in content:
            raise ValueError("الملف يحتوي على محارف غير مدعومة")
        try:
            dataframe = pd.read_csv(io.BytesIO(content), sep=None, engine="python", nrows=MAX_ROWS + 1)
        except UnicodeDecodeError:
            try:
                dataframe = pd.read_csv(io.BytesIO(content), sep=None, engine="python", encoding="latin-1", nrows=MAX_ROWS + 1)
            except Exception as exc:
                raise ValueError("تعذر قراءة CSV؛ استخدم UTF-8 أو CSV صالحاً") from exc
        except Exception as exc:
            raise ValueError("تعذر تحليل CSV؛ تأكد من وجود صف عناوين وقيم مفصولة بشكل صحيح") from exc
        if dataframe.empty:
            raise ValueError("لا يحتوي CSV على صفوف بيانات")
        if len(dataframe) > MAX_ROWS:
            raise ValueError(f"عدد الصفوف يتجاوز الحد المسموح ({MAX_ROWS:,})")
        if len(dataframe.columns) > MAX_COLUMNS:
            raise ValueError(f"عدد الأعمدة يتجاوز الحد المسموح ({MAX_COLUMNS})")
        dataframe.columns = [str(column).strip() or f"column_{index + 1}" for index, column in enumerate(dataframe.columns)]
        return dataframe

    def _profile_agent(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
        categorical_columns = [column for column in dataframe.columns if column not in numeric_columns]
        missing_by_column = {
            column: int(count)
            for column, count in dataframe.isna().sum().items()
            if int(count) > 0
        }
        numeric_summary: dict[str, dict[str, Any]] = {}
        for column in numeric_columns[:20]:
            values = dataframe[column].dropna()
            numeric_summary[column] = {
                "min": _native(values.min()) if not values.empty else None,
                "mean": _native(values.mean()) if not values.empty else None,
                "median": _native(values.median()) if not values.empty else None,
                "max": _native(values.max()) if not values.empty else None,
                "std": _native(values.std()) if not values.empty else None,
            }
        categories: dict[str, list[dict[str, Any]]] = {}
        for column in categorical_columns[:15]:
            counts = dataframe[column].astype("string").fillna("(فارغ)").value_counts().head(3)
            categories[column] = [
                {"value": str(value), "count": int(count), "share": _percentage(count / len(dataframe))}
                for value, count in counts.items()
            ]
        return {
            "rows": int(len(dataframe)),
            "columns": int(len(dataframe.columns)),
            "column_names": dataframe.columns.tolist(),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "dtypes": {column: str(dtype) for column, dtype in dataframe.dtypes.items()},
            "missing_cells": int(dataframe.isna().sum().sum()),
            "missing_by_column": missing_by_column,
            "duplicates": int(dataframe.duplicated().sum()),
            "numeric_summary": numeric_summary,
            "top_categories": categories,
        }

    def _insight_agent(self, dataframe: pd.DataFrame, overview: dict[str, Any]) -> dict[str, Any]:
        numeric_columns = overview["numeric_columns"]
        correlations: list[dict[str, Any]] = []
        if len(numeric_columns) >= 2:
            matrix = dataframe[numeric_columns].corr(numeric_only=True)
            for index, left in enumerate(numeric_columns):
                for right in numeric_columns[index + 1 :]:
                    value = matrix.loc[left, right]
                    if pd.notna(value):
                        correlations.append({"left": left, "right": right, "correlation": round(float(value), 4)})
            correlations.sort(key=lambda item: abs(item["correlation"]), reverse=True)
        spreads = []
        for column, stats in overview["numeric_summary"].items():
            if stats["std"] is not None:
                spreads.append({"column": column, "std": stats["std"]})
        spreads.sort(key=lambda item: item["std"] or 0, reverse=True)
        dominant = []
        for column, values in overview["top_categories"].items():
            if values:
                dominant.append({"column": column, **values[0]})
        if correlations:
            top = correlations[0]
            headline = f"أقوى علاقة رقمية بين {top['left']} و{top['right']} بمعامل {top['correlation']}."
        elif spreads:
            top = spreads[0]
            headline = f"أعلى تباين رقمي يظهر في العمود {top['column']} (انحراف معياري {top['std']})."
        elif dominant:
            top = dominant[0]
            headline = f"أكثر فئة تكراراً في {top['column']} هي {top['value']} بنسبة {top['share']}%."
        else:
            headline = "الملف قابل للقراءة، لكنه يحتاج حقولاً قابلة للقياس أو التصنيف لاستخراج استنتاجات أعمق."
        return {
            "headline": headline,
            "top_correlations": correlations[:3],
            "highest_spread": spreads[:3],
            "dominant_categories": dominant[:3],
        }

    def _sales_agent(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        """Recognize common retail columns and calculate explainable commercial metrics."""
        aliases = {str(column).casefold().replace(" ", ""): str(column) for column in dataframe.columns}
        quantity = aliases.get("quantity")
        unit_price = aliases.get("unitprice") or aliases.get("price")
        invoice = aliases.get("invoiceno") or aliases.get("invoice") or aliases.get("orderid")
        product = aliases.get("description") or aliases.get("product") or aliases.get("productname")
        country = aliases.get("country") or aliases.get("market")
        customer = aliases.get("customerid") or aliases.get("customer")
        if not quantity or not unit_price:
            return {"detected": False, "reason": "لم تُكتشف حقول كمية وسعر موحدة؛ تم تنفيذ التحليل العام فقط."}

        sales = dataframe.copy()
        sales["__quantity"] = pd.to_numeric(sales[quantity], errors="coerce").fillna(0)
        sales["__unit_price"] = pd.to_numeric(sales[unit_price], errors="coerce").fillna(0)
        sales["__line_value"] = sales["__quantity"] * sales["__unit_price"]
        cancelled = pd.Series(False, index=sales.index)
        if invoice:
            cancelled = sales[invoice].astype("string").str.casefold().str.startswith("c", na=False)
        completed = sales.loc[~cancelled].copy()
        net_revenue = float(sales["__line_value"].sum())
        completed_revenue = float(completed["__line_value"].sum())
        cancellation_value = float(sales.loc[cancelled, "__line_value"].sum())
        orders = int(completed[invoice].nunique()) if invoice else None
        customers = int(completed[customer].nunique()) if customer else None
        average_order = round(completed_revenue / orders, 2) if orders else None

        def ranked(column: str | None, value_column: str = "__line_value") -> list[dict[str, Any]]:
            if not column:
                return []
            grouped = completed.groupby(column, dropna=True)[value_column].sum().sort_values(ascending=False).head(5)
            return [{"name": str(name), "revenue": round(float(value), 2)} for name, value in grouped.items()]

        return {
            "detected": True,
            "quantity_column": quantity,
            "unit_price_column": unit_price,
            "net_revenue": round(net_revenue, 2),
            "completed_revenue": round(completed_revenue, 2),
            "cancellation_value": round(cancellation_value, 2),
            "cancellation_rows": int(cancelled.sum()),
            "completed_orders": orders,
            "unique_customers": customers,
            "average_order_value": average_order,
            "top_markets": ranked(country),
            "top_products": ranked(product),
        }

    def _quality_agent(self, dataframe: pd.DataFrame, overview: dict[str, Any]) -> dict[str, Any]:
        rows = max(1, overview["rows"])
        columns = max(1, overview["columns"])
        missing_rate = overview["missing_cells"] / (rows * columns)
        duplicate_rate = overview["duplicates"] / rows
        constant_columns = [column for column in dataframe.columns if dataframe[column].nunique(dropna=False) <= 1]
        outlier_count = 0
        for column in overview["numeric_columns"]:
            series = dataframe[column].dropna()
            if len(series) < 4:
                continue
            q1, q3 = series.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                outlier_count += int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
        numeric_cells = max(1, rows * max(1, len(overview["numeric_columns"])))
        outlier_rate = outlier_count / numeric_cells
        penalty = (missing_rate * 55) + (duplicate_rate * 25) + ((len(constant_columns) / columns) * 10) + (outlier_rate * 10)
        score = max(0, min(100, round(100 - penalty)))
        if score >= 90:
            status = "ممتازة"
        elif score >= 75:
            status = "جيدة"
        elif score >= 55:
            status = "تحتاج تنظيفاً"
        else:
            status = "تحتاج معالجة قبل اتخاذ القرار"
        recommendations = []
        if missing_rate > 0:
            recommendations.append("عالج القيم الناقصة أو وضح سبب بقائها قبل بناء قرار عليها.")
        if duplicate_rate > 0:
            recommendations.append("راجع الصفوف المكررة قبل حساب المقاييس النهائية.")
        if constant_columns:
            recommendations.append(f"فكر في استبعاد الأعمدة الثابتة: {', '.join(constant_columns[:4])}.")
        if outlier_rate > 0.03:
            recommendations.append("راجع القيم الشاذة لأنها قد تغير المتوسطات والارتباطات.")
        if not recommendations:
            recommendations.append("جودة البيانات مناسبة للمرحلة التالية من التحليل أو بناء نموذج أولي.")
        return {
            "score": score,
            "status": status,
            "missing_rate": _percentage(missing_rate),
            "duplicate_rate": _percentage(duplicate_rate),
            "outlier_rate": _percentage(outlier_rate),
            "constant_columns": constant_columns,
            "recommendations": recommendations,
        }

    def _agent_outputs(self, overview: dict[str, Any], insights: dict[str, Any], quality: dict[str, Any], sales: dict[str, Any]) -> list[dict[str, Any]]:
        outputs = [
            {
                "agent": "Data Profiling Agent",
                "status": "completed",
                "finding": f"تم فحص {overview['rows']} صفاً و{overview['columns']} عموداً؛ {len(overview['numeric_columns'])} أعمدة رقمية و{len(overview['categorical_columns'])} فئوية.",
            },
            {
                "agent": "Insight Agent",
                "status": "completed",
                "finding": insights["headline"],
            },
            {
                "agent": "Data Quality Agent",
                "status": "completed",
                "finding": f"درجة الجودة {quality['score']}/100 ({quality['status']}) مع نسبة قيم ناقصة {quality['missing_rate']}%.",
            },
        ]
        if sales["detected"]:
            outputs.append(
                {
                    "agent": "Sales Intelligence Agent",
                    "status": "completed",
                    "finding": (
                        f"صافي المبيعات المحسوب {sales['net_revenue']:.2f}؛ "
                        f"الطلبات المكتملة {sales['completed_orders'] or 'غير متاح'}؛ "
                        f"وقيمة الإلغاءات {sales['cancellation_value']:.2f}."
                    ),
                }
            )
        return outputs

    def _synthesize(self, source_name: str, overview: dict[str, Any], insights: dict[str, Any], quality: dict[str, Any], sales: dict[str, Any]) -> str:
        recommendations = " ".join(quality["recommendations"][:2])
        sales_text = ""
        if sales["detected"]:
            sales_text = (
                f" وكيل المبيعات قدّر صافي المبيعات بـ {sales['net_revenue']:.2f}، "
                f"والمبيعات المكتملة بـ {sales['completed_revenue']:.2f}."
            )
        return (
            f"تم تحليل ملف {Path(source_name).name} محلياً عبر وكلاء متخصصين. "
            f"يتكون من {overview['rows']} صفاً و{overview['columns']} عموداً. "
            f"{insights['headline']} "
            f"درجة جودة البيانات {quality['score']}/100 ({quality['status']})."
            f"{sales_text} الخطوة المقترحة: {recommendations}"
        )
