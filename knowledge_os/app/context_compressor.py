import asyncio
import re

# Context Analyzer for smart compression
try:
    from context_analyzer import ContextAnalyzer
except ImportError:
    ContextAnalyzer = None


class ContextCompressor:
    """Utility to compress prompt context locally before sending to cloud LLM."""

    @staticmethod
    def compress_logs(logs: str, max_lines: int = 50) -> str:
        """Compress logs by keeping only errors and recent lines."""
        lines = logs.splitlines()
        if len(lines) <= max_lines:
            return logs

        critical_lines = [
            l
            for l in lines
            if any(keyword in l.upper() for keyword in ["ERROR", "CRITICAL", "EXCEPTION", "FAIL"])
        ]

        # Keep recent lines
        recent_lines = lines[-max_lines // 2 :]

        # Merge and deduplicate
        compressed = list(dict.fromkeys(critical_lines + recent_lines))
        return "\n".join(compressed[-max_lines:])

    @staticmethod
    def summarize_knowledge(knowledge_text: str) -> str:
        """Summarize knowledge nodes to key points."""
        # Simple extraction of titles/first sentences
        blocks = knowledge_text.split("\n")
        summary = []
        for block in blocks:
            if block.strip():
                # Take only the first part before detailed description
                summary.append(block[:200] + "...")
        return "\n".join(summary)

    @staticmethod
    def strip_metadata(prompt: str) -> str:
        """Remove unnecessary metadata/whitespace from prompt."""
        # Remove multiple newlines
        prompt = re.sub(r"\n{3,}", "\n\n", prompt)
        # Remove trailing/leading whitespace per line
        prompt = "\n".join([l.strip() for l in prompt.splitlines()])
        return prompt.strip()

    @staticmethod
    def squeeze_prompt(prompt: str) -> str:
        """
        [SINGULARITY 24.0] Aggressive Prompt Squeezing.
        Removes filler words, polite forms, and redundant instructions.
        Reduces token count by 20-30% without losing core meaning.
        """
        if not prompt:
            return ""

        # 1. Список стоп-фраз и "воды"
        fillers = [
            r"пожалуйста",
            r"будьте добры",
            r"если вас не затруднит",
            r"я хотел бы попросить вас",
            r"не могли бы вы",
            r"подскажите пожалуйста",
            r"заранее спасибо",
            r"с уважением",
            r"надеюсь на ваш ответ",
            r"в данном контексте",
            r"как уже упоминалось ранее",
            r"хочу обратить ваше внимание на то что",
            r"важно отметить что",
            r"стоит упомянуть что",
        ]

        squeezed = prompt
        for filler in fillers:
            squeezed = re.sub(filler, "", squeezed, flags=re.IGNORECASE)

        # 2. Сжатие избыточных пробелов и пустых строк
        squeezed = re.sub(r" {2,}", " ", squeezed)
        squeezed = re.sub(r"\n{3,}", "\n\n", squeezed)

        # 3. Удаление дублирующихся строк (SINGULARITY 25.0 FIX)
        lines = squeezed.splitlines()
        unique_lines = []
        seen = set()
        for line in lines:
            clean_line = line.strip()
            if clean_line and clean_line not in seen:
                unique_lines.append(line)
                seen.add(clean_line)
            elif not clean_line:
                unique_lines.append(line)

        return "\n".join(unique_lines).strip()

    @classmethod
    def compress_all(cls, prompt: str) -> str:
        """Apply all compression techniques."""
        if not prompt:
            return ""
        prompt = cls.strip_metadata(prompt)
        prompt = cls.squeeze_prompt(prompt)  # [SINGULARITY 24.0]
        return prompt

    @classmethod
    async def compress_smart(
        cls, context: str, query: str, max_length: int = 2000, aggressive: bool = True
    ) -> str:
        """
        Умное сжатие контекста с использованием семантического анализа.

        Args:
            context: Полный контекст
            query: Запрос пользователя
            max_length: Максимальная длина
            aggressive: Агрессивное сжатие (более низкий порог релевантности)

        Returns:
            Сжатый контекст
        """
        if ContextAnalyzer:
            # Более агрессивный порог для экономии токенов (0.65 вместо 0.7)
            relevance_threshold = 0.65 if aggressive else 0.7
            analyzer = ContextAnalyzer(relevance_threshold=relevance_threshold)
            return await analyzer.compress_context(context, query, max_length)
        else:
            # Fallback к простому сжатию
            if len(context) <= max_length:
                return context
            return context[:max_length] + "..."
