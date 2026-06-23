import { defineStore } from "pinia";

export interface PricingItem {
  id: string;
  name: string;
  price: number;
}

export interface GlobalPricing {
  mesh: PricingItem[];
  profiles: PricingItem[];
  components: PricingItem[];
  services: PricingItem[];
  markup: {
    dealer: number;
    client: number;
    clientFactorFromCost?: number;
    manufacturing_base: number;
    manufacturing_percent: number;
    measurement_base: number;
    measurement_percent: number;
    measurement_profit_factor: number;
    urgent_profit_factor: number;
    installation_profit_factor: number;
    delivery_profit_factor: number;
  };
}

export const usePricingStore = defineStore("pricing", {
  state: () => ({
    pricing: null as GlobalPricing | null,
    isLoading: false,
  }),
  actions: {
    async fetchPricing(retry = true, ssrOrigin?: string) {
      this.isLoading = true;
      try {
        const runtimeConfig = useRuntimeConfig();
        let apiBase = import.meta.server
          ? runtimeConfig.public.apiBase
          : runtimeConfig.public.apiUrl || "";

        // SSR fallback: если внутренний API hostname недоступен, берём API текущего домена.
        if (import.meta.server && ssrOrigin) {
          apiBase = `${ssrOrigin.replace(/\/$/, "")}/api`;
        }

        // На SSR apiBase уже включает /api (http://api:8080/api), поэтому путь должен быть /v1/...
        // На клиенте apiBase пустой, поэтому путь должен быть /api/v1/...
        const fetchPath =
          apiBase && apiBase.startsWith("http")
            ? "v1/pricing"
            : "/api/v1/pricing";

        if (import.meta.server) {
          // console.error(`[SSR_PRICING] Fetching from ${apiBase} with path ${fetchPath}`)
        }

        const response = (await ($fetch as any)(fetchPath, {
          baseURL: apiBase,
          timeout: 8000,
        })) as GlobalPricing;

        // Добавляем clientFactorFromCost из client, если его нет в ответе
        if (response.markup && !response.markup.clientFactorFromCost) {
          response.markup.clientFactorFromCost = response.markup.client;
        }

        this.pricing = response;
        if (import.meta.server) {
          // console.error(`[SSR_PRICING] Loaded markup: ${JSON.stringify(response.markup)}`)
        }
      } catch (e) {
        console.error("Failed to fetch global pricing", e);
        // Один повтор через 1.5 с при холодном старте API (Docker/VDS)
        if (retry) {
          setTimeout(() => this.fetchPricing(false), 1500);
          return;
        }
      } finally {
        this.isLoading = false;
      }
    },
  },
});
