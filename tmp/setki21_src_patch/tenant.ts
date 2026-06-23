import { defineStore } from "pinia";

export const useTenantStore = defineStore("tenant", () => {
  const config = ref({
    dealer_id: "",
    dealer_name: "",
    city: "",
    phone: "",
    email: "" as string,
    branding: {
      logo_url: "",
      favicon_url: "",
      primary_color: "",
      short_description: "",
      working_hours: "",
    },
    contacts: {
      phones: [],
      emails: [],
      branches: [] as { id: string; name: string; address: string }[],
    },
    seo: {
      title: "",
      description: "",
      keywords: "",
      verification_tag: "",
      analytics_code: "",
      pages: {} as Record<string, { title?: string; description?: string }>,
    },
    legal: {
      requisites: "",
      privacy_policy_url: "/privacy",
    },
    margin_config: {
      base_margin_percent: 0,
      city_multiplier: 1,
      branch_multiplier: 1,
      urgent_margin_percent: null as number | null,
      delivery_margin_percent: null as number | null,
      installation_margin_percent: null as number | null,
      measurement_margin_percent: null as number | null,
    },
  });

  const isLoaded = ref(false);

  const fetchConfig = async (ssrOrigin?: string) => {
    try {
      const runtimeConfig = useRuntimeConfig();
      const apiBase = runtimeConfig.public.apiUrl || "";
      const route = useRoute();

      // Запрос конфига — на текущий origin, чтобы бэкенд получил Host дилера и вернул его конфиг (фавикон и лого дилера, не головного сайта)
      // На клиенте: baseURL '' = текущий origin. На SSR: используем apiBase (http://api:8080/api) с Host заголовком
      const configBaseUrl =
        process.client && typeof window !== "undefined"
          ? ""
          : runtimeConfig.public.apiBase;

      const dealerId = !route.path.startsWith("/admin")
        ? route.query.dealer_id
        : null;
      const queryParams = dealerId ? { dealer_id: String(dealerId) } : {};

      const headers: Record<string, string> = {};
      if (ssrOrigin) {
        try {
          const url = new URL(ssrOrigin);
          let host = url.host;
          console.error(`[SSR_DEBUG] ORIGINAL_HOST: ${host}`);
          if (
            host === "localhost:3003" ||
            host === "127.0.0.1:3003" ||
            host === "0.0.0.0:3003"
          ) {
            host = "setkimoskitki.ru";
            console.error(`[SSR_DEBUG] MAPPED_HOST: ${host}`);
          }
          headers["host"] = host;
          headers["x-forwarded-host"] = host;
          headers["x-forwarded-proto"] = url.protocol.replace(":", "");
        } catch (e) {
          console.error("Invalid ssrOrigin URL:", ssrOrigin);
        }
      }

      if (import.meta.server) {
        // console.log(`[SSR] Fetching config from ${configBaseUrl}/api/v1/tenant/config with Host: ${headers['Host'] || 'none'}`)
      }

      // На SSR apiBase уже включает /api (http://api:8080/api), поэтому путь должен быть /v1/...
      // На клиенте apiBase пустой, поэтому путь должен быть /api/v1/...
      const fetchPath =
        apiBase && apiBase.startsWith("http")
          ? "v1/tenant/config"
          : "/api/v1/tenant/config";

      if (import.meta.server) {
        // console.log(`[SSR] Fetching config from "${apiBase}" with path "${fetchPath}" and Host: ${headers['host'] || 'none'}`)
      }

      // Используем полный URL для SSR всегда.
      // При наличии ssrOrigin используем API текущего домена как fallback,
      // чтобы не зависеть от внутреннего DNS имени контейнера API.
      const ssrBaseUrl = ssrOrigin
        ? `${ssrOrigin.replace(/\/$/, "")}/api`
        : runtimeConfig.public.apiBase;
      const cleanSsrBaseUrl = ssrBaseUrl.endsWith("/")
        ? ssrBaseUrl.slice(0, -1)
        : ssrBaseUrl;

      const finalFetchPath = import.meta.server
        ? `${cleanSsrBaseUrl}/v1/tenant/config`
        : "/api/v1/tenant/config";

      if (import.meta.server) {
        // console.log(`[SSR] Fetching config from "${finalFetchPath}" with Host: ${headers['host'] || 'none'}`)
      }

      // ВАЖНО: На SSR используем нативный fetch или $fetch с полным URL,
      // чтобы избежать резолвинга Nuxt как внутреннего роута.
      let data: any = null;
      if (import.meta.server) {
        // Проверяем, является ли путь абсолютным URL
        let fetchUrl = finalFetchPath;
        if (!fetchUrl.startsWith("http")) {
          fetchUrl = `${cleanSsrBaseUrl}/v1/tenant/config`;
        }

        const url = new URL(fetchUrl);
        if (queryParams.dealer_id)
          url.searchParams.set("dealer_id", queryParams.dealer_id as string);

        // Очищаем заголовки для нативного fetch
        const cleanHeaders: Record<string, string> = {};
        // Принудительно очищаем Host от лишних пробелов и символов
        if (headers["host"]) cleanHeaders["host"] = headers["host"].trim();
        if (headers["x-forwarded-host"])
          cleanHeaders["x-forwarded-host"] = headers["x-forwarded-host"].trim();
        if (headers["x-forwarded-proto"])
          cleanHeaders["x-forwarded-proto"] =
            headers["x-forwarded-proto"].trim();

        // Добавляем User-Agent, чтобы бэкенд не блокировал запрос
        cleanHeaders["user-agent"] = "Mozilla/5.0 (Nuxt SSR)";

        // ВАЖНО: Принудительно выводим в stdout через console.error, так как Nuxt может перехватывать console.log
        console.error(
          `[SSR_DEBUG] FETCHING: ${url.toString()} with host: ${cleanHeaders["host"]}`,
        );

        try {
          const response = await fetch(url.toString(), {
            headers: cleanHeaders,
          });
          // console.error(`[SSR_DEBUG] RESPONSE: ${response.status}`)
          if (response.ok) {
            data = await response.json();
            // console.error(`[SSR_DEBUG] DATA_TAG: ${data?.seo?.verification_tag}`)
            // Принудительно обновляем состояние стора
            config.value = { ...config.value, ...data };
          } else {
            const body = await response.text();
            // console.error(`[SSR_DEBUG] ERROR_BODY: ${body}`)
          }
        } catch (fetchError) {
          // console.error(`[SSR_DEBUG] EXCEPTION:`, fetchError)
        }
      } else {
        // На клиенте используем $fetch, заголовки будут переданы автоматически или из аргументов
        const clientHeaders: Record<string, string> = {};
        if (headers["host"]) clientHeaders["host"] = headers["host"];

        data = await $fetch(finalFetchPath, {
          query: queryParams,
          headers: clientHeaders,
        });
      }

      if (data) {
        // Полная замена конфига из API; email и contacts.emails нужны для заявок дилера (callback)
        const updatedConfig = { ...config.value, ...data };

        // Убеждаемся, что email дилера попал в основное поле email, если он есть в корне ответа
        if (data.email) {
          updatedConfig.email = data.email;
        }

        config.value = updatedConfig;

        const base =
          process.client && typeof window !== "undefined"
            ? window.location.origin
            : ssrOrigin || (runtimeConfig.public.apiUrl as string) || "";
        const baseClean = base ? base.replace(/\/$/, "") : "";
        // Логотип: относительный путь → полный URL от текущего origin (SSR: домен запроса)
        if (data.branding?.logo_url && data.branding.logo_url.startsWith("/")) {
          config.value.branding.logo_url = baseClean + data.branding.logo_url;
        }
        // Фавикон: favicon_url из конфига или автогенерируем из logo_url
        if (
          data.branding?.favicon_url &&
          data.branding.favicon_url.startsWith("/")
        ) {
          config.value.branding.favicon_url =
            baseClean + data.branding.favicon_url;
        } else if (data.branding?.favicon_url) {
          config.value.branding.favicon_url = data.branding.favicon_url;
        } else if (data.branding?.logo_url) {
          // favicon_url не задан — автоматически используем logo_url как фавикон
          config.value.branding.favicon_url = data.branding.logo_url.startsWith(
            "/",
          )
            ? baseClean + data.branding.logo_url
            : data.branding.logo_url;
        }
        isLoaded.value = true;

        // Применяем основной цвет к CSS переменной (только на клиенте)
        if (process.client && data.branding?.primary_color) {
          document.documentElement.style.setProperty(
            "--brand-blue",
            data.branding.primary_color,
          );
        }
      }
    } catch (e) {
      console.error("Failed to fetch tenant config", e);
    }
  };

  return {
    config,
    isLoaded,
    fetchConfig,
  };
});
