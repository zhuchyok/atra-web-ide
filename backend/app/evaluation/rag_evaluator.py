"""
Фаза 4, неделя 3: оценка качества RAG ответов.

Метрики: faithfulness (верность контексту), relevance (релевантность запросу),
coherence (связность), BLEU/ROUGE при наличии reference.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """
    Оценка качества RAG ответов по нескольким метрикам.
    Используется в скрипте evaluate_rag_quality.py и при необходимости в CI.
    """

    async def evaluate_response(
        self,
        query: str,
        response: str,
        context: List[str],
        reference: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Оценка ответа по метрикам.
        Возвращает словарь: faithfulness, relevance, coherence; при наличии reference — bleu, rouge.
        """
        result: Dict[str, float] = {}
        result["faithfulness"] = self._calculate_faithfulness(response, context)
        result["relevance"] = self._calculate_relevance(response, query, reference)
        result["coherence"] = self._calculate_coherence(response)
        if reference:
            result["bleu"] = self._calculate_bleu(response, reference)
            result["rouge"] = self._calculate_rouge(response, reference)
        return result

    def _calculate_faithfulness(self, response: str, context: List[str]) -> float:
        """
        Верность контексту: доля слов/фраз ответа, встречающихся в контексте.
        Упрощённая версия; для продакшена — NLI-модель.
        """
        if not response or not context:
            return 0.0
        ctx_text = " ".join(context).lower()
        resp_words = set(re.findall(r"\w+", response.lower()))
        if not resp_words:
            return 1.0
        in_ctx = sum(1 for w in resp_words if w in ctx_text)
        return in_ctx / len(resp_words)

    def _calculate_relevance(
        self, response: str, query: str, reference: Optional[str] = None
    ) -> float:
        """
        Релевантность: при наличии reference — F1 по word overlap (recall + precision),
        чтобы не штрафовать короткие корректные ответы; иначе — query ↔ response.
        """
        if not response:
            return 0.0
        r_words = set(re.findall(r"\w+", response.lower()))
        if reference and reference.strip():
            ref_words = set(re.findall(r"\w+", reference.lower()))
            if not ref_words:
                return 0.5
            inter = len(ref_words & r_words)
            recall = inter / len(ref_words)  # доля эталона в ответе
            precision = inter / len(r_words) if r_words else 0.0  # доля ответа в эталоне
            if recall + precision == 0:
                return 0.0
            f1 = 2 * recall * precision / (recall + precision)
            return min(1.0, f1 * 1.1)  # короткий правильный ответ: precision≈1 → хороший score
        if not query:
            return 0.5
        q_words = set(re.findall(r"\w+", query.lower()))
        if not q_words:
            return 0.5
        overlap = len(q_words & r_words) / len(q_words)
        return min(1.0, overlap + 0.3)

    def _calculate_coherence(self, response: str) -> float:
        """
        Связность: базовая эвристика (длина, наличие точек, без обрывков).
        Для продакшена — модель связности или LLM-as-judge.
        """
        if not response or len(response.strip()) < 10:
            return 0.0
        score = 0.5
        if "." in response or "!" in response or "?" in response:
            score += 0.2
        if len(response) > 50:
            score += 0.2
        if not re.search(r"\s{5,}", response):  # нет огромных пробелов
            score += 0.1
        return min(1.0, score)

    def _calculate_bleu(self, response: str, reference: str) -> float:
        """BLEU (упрощённо): совпадение 1-gram и 2-gram."""
        try:
            from nltk.translate.bleu_score import sentence_bleu
            ref = [reference.split()]
            hyp = response.split()
            return float(sentence_bleu(ref, hyp, weights=(0.5, 0.5)))
        except ImportError:
            # Fallback: доля общих слов
            r_w = set(response.lower().split())
            ref_w = set(reference.lower().split())
            if not ref_w:
                return 0.0
            return len(r_w & ref_w) / len(ref_w)
        except Exception as e:
            logger.debug("BLEU failed: %s", e)
            return 0.0

    def _calculate_rouge(self, response: str, reference: str) -> float:
        """ROUGE (упрощённо): recall по 1-gram."""
        try:
            from rouge_score import rouge_scorer
            scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=False)
            s = scorer.score(reference, response)
            return s["rouge1"].recall
        except ImportError:
            r_w = set(response.lower().split())
            ref_w = set(reference.lower().split())
            if not ref_w:
                return 0.0
            return len(r_w & ref_w) / len(ref_w)
        except Exception as e:
            logger.debug("ROUGE failed: %s", e)
            return 0.0
