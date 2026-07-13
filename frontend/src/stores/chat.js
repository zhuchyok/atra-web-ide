import { writable, derived, get } from "svelte/store";

// Сообщения чата
export const messages = writable([]);

// Текущий выбранный эксперт
export const selectedExpert = writable(null);

// Список экспертов
export const experts = writable([]);

// Статус загрузки
export const isLoading = writable(false);

// Статус стриминга
export const isStreaming = writable(false);

// Ошибка
export const error = writable(null);

// Режим чата (как в Cursor): agent | plan | ask
export const chatMode = writable("agent");

// Добавить сообщение (assistant может иметь steps — шаги агента как в Cursor)
export function addMessage(role, content, expertName = null) {
  messages.update((msgs) => [
    ...msgs,
    {
      id: Date.now(),
      role,
      content: content ?? "",
      expertName,
      steps: role === "assistant" ? [] : undefined,
      timestamp: new Date().toISOString(),
    },
  ]);
}

// Добавить шаг агента к последнему сообщению (thought, exploration, action, clarification)
export function appendStep(step) {
  messages.update((msgs) => {
    if (msgs.length === 0) return msgs;
    const last = msgs[msgs.length - 1];
    if (last.role !== "assistant" || !Array.isArray(last.steps)) return msgs;
    return [...msgs.slice(0, -1), { ...last, steps: [...last.steps, step] }];
  });
}

// Обновить последнее сообщение (для стриминга)
export function updateLastMessage(content) {
  console.log("updateLastMessage called with:", content?.slice(0, 50));
  messages.update((msgs) => {
    if (msgs.length === 0) {
      console.warn("No messages to update!");
      return msgs;
    }
    const last = msgs[msgs.length - 1];
    const newContent = (last.content || "") + content;
    console.log("Updated content length:", newContent.length);
    return [...msgs.slice(0, -1), { ...last, content: newContent }];
  });
}

// Очистить чат
export function clearMessages() {
  messages.set([]);
}

// Загрузить экспертов с API
export async function loadExperts() {
  try {
    // Используем порт 8080 для FastAPI Backend
    const response = await fetch(`/api/experts`);
    if (response.ok) {
      const data = await response.json();
      experts.set(data);
      if (data.length > 0) {
        selectedExpert.set(data[0]);
      }
    } else {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
  } catch (e) {
    console.error("Failed to load experts:", e);
    // Fallback - только Виктория
    const victoria = { id: "1", name: "Виктория", role: "Team Lead" };
    experts.set([victoria]);
    selectedExpert.set(victoria);
  }
}

// Ключевые слова для диалогов экспертов
const EXPERT_DIALOGUE_KEYWORDS = [
  "дебаты",
  "дискуссия",
  "спор",
  "мнения",
  "эксперты",
  "обсудить",
  "debate",
  "discuss",
  "experts",
];

function detectDialogueMode(content) {
  const lower = content.toLowerCase();
  if (
    lower.includes("дебаты") ||
    lower.includes("debate") ||
    lower.includes("спор")
  )
    return "debate";
  if (
    lower.includes("дебаты") ||
    lower.includes("debate") ||
    lower.includes("спор")
  )
    return "debate";
  if (
    lower.includes("обсудить") ||
    lower.includes("discuss") ||
    lower.includes("спроектируй")
  )
    return "collaboration";
  if (
    lower.includes("совет") ||
    lower.includes("эксперты") ||
    lower.includes("мнения")
  )
    return "sequential";
  return "debate"; // По умолчанию debate
}

function isExpertDialogueRequest(content) {
  const lower = content.toLowerCase();
  return EXPERT_DIALOGUE_KEYWORDS.some((kw) => lower.includes(kw));
}

// Отправить сообщение через SSE
export async function sendMessage(content, mode = null) {
  const expertValue = get(selectedExpert);
  const modeValue = mode ?? get(chatMode);

  addMessage("user", content);
  isStreaming.set(true);
  isLoading.set(true);
  error.set(null);
  addMessage("assistant", "", expertValue?.name);

  try {
    const { fetchSSE } = await import("../utils/sse.js");

    // Проверяем запрос на диалог экспертов
    if (isExpertDialogueRequest(content)) {
      const dialogueMode = detectDialogueMode(content);
      await fetchSSE(
        `/api/expert-dialogue/stream`,
        {
          topic: content,
          mode: dialogueMode,
          beautiful_mode: true,
        },
        (data) => {
          if (data.type === "log" || data.type === "start") {
            appendStep({
              title: "🎭 Диалог экспертов",
              content: data.content,
              stepType: "thought",
            });
          } else if (data.type === "opinion") {
            appendStep({
              title: data.expert,
              content: data.content,
              stepType: "action",
            });
          } else if (data.type === "complete") {
            updateLastMessage(
              `✅ Решение: ${data.final_decision}\n\n📊 Consensus: ${(data.consensus_score * 100).toFixed(0)}%`,
            );
          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        },
      );
    } else {
      // Обычный чат с Victoria
      await fetchSSE(
        `/api/chat/stream`,
        {
          content: content,
          expert_name: expertValue?.name,
          mode: modeValue,
        },
        (data) => {
          if (data.type === "chunk") {
            updateLastMessage(data.content);
          } else if (data.type === "step") {
            appendStep({
              title: data.title,
              content: data.content,
              stepType: data.step_type || "thought",
            });
          } else if (data.type === "error") {
            throw new Error(data.content);
          }
        },
      );
    }
  } catch (e) {
    let errorMessage = e.message || "Ошибка при отправке сообщения.";
    if (e.message?.includes("503") || e.message?.includes("service_busy")) {
      errorMessage = "Сервер перегружен. Подождите и попробуйте снова.";
    } else if (
      e.message?.includes("Failed to fetch") ||
      e.message?.includes("NetworkError")
    ) {
      errorMessage =
        "Нет связи с сервером. Проверьте, что бэкенд запущен (порт 8080).";
    }
    error.set(errorMessage);
    console.error("Chat error:", e);

    // Удаляем пустое сообщение ассистента при ошибке
    messages.update((msgs) => {
      if (
        msgs.length > 0 &&
        msgs[msgs.length - 1].role === "assistant" &&
        !msgs[msgs.length - 1].content
      ) {
        return msgs.slice(0, -1);
      }
      return msgs;
    });
  } finally {
    isStreaming.set(false);
    isLoading.set(false);
  }
}
