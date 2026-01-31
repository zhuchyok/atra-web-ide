import re
import asyncio

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
            
        critical_lines = [l for l in lines if any(keyword in l.upper() for keyword in ["ERROR", "CRITICAL", "EXCEPTION", "FAIL"])]
        
        # Keep recent lines
        recent_lines = lines[-max_lines//2:]
        
        # Merge and deduplicate
        compressed = list(dict.fromkeys(critical_lines + recent_lines))
        return "\n".join(compressed[-max_lines:])

    @staticmethod
    def summarize_knowledge(knowledge_text: str) -> str:
        """Summarize knowledge nodes to key points."""
        # Simple extraction of titles/first sentences
        blocks = knowledge_text.split('\n')
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
        prompt = re.sub(r'\n{3,}', '\n\n', prompt)
        # Remove trailing/leading whitespace per line
        prompt = "\n".join([l.strip() for l in prompt.splitlines()])
        return prompt.strip()

    @classmethod
    def compress_all(cls, prompt: str) -> str:
        """Apply all compression techniques."""
        prompt = cls.strip_metadata(prompt)
        # Additional logic could be added here
        return prompt
    
    @classmethod
    async def compress_smart(cls, context: str, query: str, max_length: int = 2000, aggressive: bool = True) -> str:
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

