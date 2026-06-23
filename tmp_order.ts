import { defineStore } from "pinia";
import {
  type ColorId,
  type MeshType,
  type FrameType,
  type HandleType,
  COLOR_NAMES,
  FRAME_TYPE_NAMES,
  MESH_TYPE_NAMES,
} from "~/types/mesh";
import {
  PRICING_CONFIG,
  DELIVERY_OPTIONS,
  URGENT_ORDER_OPTION,
  MEASUREMENT_OPTION,
} from "~/constants/pricing";
import {
  computeCost,
  computeCostVstavnaya,
  costToClientPrice,
  getWork,
  getRalPaintingAmount,
  getNetRevenueAfterCard,
  roundTo,
  getConfig,
  type MarginConfig,
} from "~/services/pricing";
import { usePricingStore } from "~/stores/pricing";
import { useTenantStore } from "~/stores/tenant";

export interface OrderItem {
  id: number;
  type: MeshType;
  typeName: string;
  frameTypeName: string;
  color: string;
  width: number;
  height: number;
  count: number;
  price: number;
  measurementMethod: string;
}

export const useOrderStore = defineStore("order", {
  state: () => ({
    /** Legacy: таблица VSN не используется — вставная считается по формуле (профиль 151/153/163, тип полотна учитывается). */
    prices: {
      vstavnye: [
        1450, 1600, 1800, 1950, 2100, 2250, 2400, 2550, 2700, 2900, 3050, 3200,
        3350, 3500, 3650, 3800, 1550, 1750, 1900, 2050, 2200, 2400, 2550, 2700,
        2850, 3050, 3200, 3350, 3500, 3650, 3850, 4000, 1650, 1800, 2000, 2150,
        2300, 2450, 2650, 2800, 2950, 3150, 3300, 3450, 3600, 3800, 3950, 4100,
        1850, 2000, 2200, 2350, 2500, 2650, 2850, 3000, 3150, 3350, 3500, 3650,
        3800, 4000, 4150, 4300,
      ],
    },
    items: [] as OrderItem[],
    config: {
      type: "standart" as MeshType,
      typeName: "СТАНДАРТ",
      frameType: "standart" as FrameType,
      width: 350,
      height: 1000,
      color: 1 as ColorId,
      count: 1,
      installation: false,
      handleType: "pvc" as HandleType,
      measurementMethod: "" as "" | "stvorka" | "proem" | "old_mesh",
    },
    /** Способ получения: по умолчанию доставка (Чебоксары и Новочебоксарск) */
    delivery: "Доставка",
    deliveryPrice: 400,
    /** Замер Чебоксары и Новочебоксарск (вторая услуга, можно выбрать вместе с доставкой/скидкой) */
    measurementSelected: false,
    measurementPrice: 0,
    /** Приоритетный срочный заказ +400 ₽ (только при заказе с монтажом) */
    discountType: "" as "" | "srochnyi",
  }),
  getters: {
    /** В корзине все позиции без монтажа */
    allItemsWithoutInstallation(state): boolean {
      if (state.items.length === 0) return false;
      return state.items.every((item) => !item.typeName.includes(" + МОНТАЖ"));
    },
    /** В корзине все позиции с монтажом */
    allItemsWithInstallation(state): boolean {
      if (state.items.length === 0) return false;
      return state.items.every((item) => item.typeName.includes(" + МОНТАЖ"));
    },
    /** В корзине есть хотя бы одна позиция без монтажа */
    hasItemsWithoutInstallation(state): boolean {
      return state.items.some((item) => !item.typeName.includes(" + МОНТАЖ"));
    },
    /** В корзине есть хотя бы одна позиция с монтажом */
    hasItemsWithInstallation(state): boolean {
      return state.items.some((item) => item.typeName.includes(" + МОНТАЖ"));
    },
    /** Смешанный заказ: и сетки с монтажом, и без — тогда только доставка */
    isMixedOrder(state): boolean {
      if (state.items.length === 0) return false;
      const hasWithout = state.items.some(
        (item) => !item.typeName.includes(" + МОНТАЖ"),
      );
      const hasWith = state.items.some((item) =>
        item.typeName.includes(" + МОНТАЖ"),
      );
      return hasWithout && hasWith;
    },
    /** Расчитанная цена доставки для клиента */
    deliveryPriceCalculated(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const p = pricingStore.pricing;
      if (!p) return 400;

      // Если заказ смешанный (есть и с монтажом, и без), используем себестоимость смежной доставки
      const baseDelivery = state.isMixedOrder
        ? (p.services.find((s: any) => s.id === "delivery_mixed")?.price ?? 100)
        : (p.services.find((s: any) => s.id === "delivery")?.price ?? 300);

      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;
      const profitFactor =
        (marginConfig?.delivery_margin_percent !== null &&
        marginConfig?.delivery_margin_percent !== undefined
          ? marginConfig.delivery_margin_percent
          : (p.markup.delivery_profit_factor ?? 33)) / 100;
      const finalPrice =
        Math.round((baseDelivery + baseDelivery * profitFactor) / 50) * 50;
      // Смешанная доставка — свой минимум (150), обычная — 400
      const minDelivery = state.isMixedOrder ? 150 : 400;
      return Math.max(finalPrice, minDelivery);
    },
    /** Расчитанная цена замера для отображения в UI */
    measurementPriceCalculated(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const p = pricingStore.pricing;
      if (!p) return 400;

      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;

      // ВАЖНО: Обновляем clientFactorFromCost в сторе, чтобы он был доступен при гидратации
      const config = getConfig(p, marginConfig);
      if (p.markup) {
        p.markup.clientFactorFromCost = config.markup.clientFactorFromCost;
        console.error(
          `[SSR_DEBUG] UPDATED clientFactorFromCost to ${p.markup.clientFactorFromCost} for host ${tenantStore.config.dealer_name}`,
        );
      }

      if (state.items.length === 0)
        return (
          (marginConfig as any)?.measurement_base ||
          p.markup.measurement_base ||
          400
        );

      const totalMaterialCost = state.items.reduce((sum, item) => {
        const colorId: ColorId =
          item.color === "КОРИЧНЕВАЯ"
            ? 2
            : item.color === "АНТРАЦИТ"
              ? 3
              : item.color === "RAL"
                ? 4
                : 1;
        const cost = item.frameTypeName.includes("ВСТАВНАЯ")
          ? computeCostVstavnaya(
              item.width,
              item.height,
              colorId,
              item.type,
              p,
              marginConfig,
            )
          : computeCost(
              item.width,
              item.height,
              colorId,
              item.type,
              p,
              marginConfig,
            );
        const work = getWork(
          item.width,
          item.height,
          colorId,
          item.type,
          item.frameTypeName.includes("ВСТАВНАЯ") ? "vstavnaya" : "standart",
          p,
          marginConfig,
        );
        return sum + (cost - work) * item.count;
      }, 0);

      const base = p.markup.measurement_base ?? 270;
      const bonus =
        totalMaterialCost * ((p.markup.measurement_percent ?? 5) / 100);
      const profit =
        totalMaterialCost *
        ((marginConfig?.measurement_margin_percent !== null &&
        marginConfig?.measurement_margin_percent !== undefined
          ? marginConfig.measurement_margin_percent
          : (p.markup.measurement_profit_factor ?? 5)) /
          100);

      const finalPrice =
        Math.round((base + (bonus || 0) + (profit || 0)) / 50) * 50;
      return Math.max(finalPrice, 400);
    },
    currentPrice(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const isMetal = state.config.handleType === "metal";

      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;

      // ВАЖНО: Обновляем clientFactorFromCost в сторе, чтобы он был доступен при гидратации
      if (pricingStore.pricing && pricingStore.pricing.markup) {
        const config = getConfig(pricingStore.pricing, marginConfig);
        pricingStore.pricing.markup.clientFactorFromCost =
          config.markup.clientFactorFromCost;
        if (import.meta.server) {
          console.error(
            `[SSR_DEBUG] UPDATED clientFactorFromCost to ${pricingStore.pricing.markup.clientFactorFromCost} in currentPrice`,
          );
        }
      }

      // Размеры теперь корректируются напрямую в config при выборе метода,
      // поэтому здесь используем значения как есть.
      const calcWidth = state.config.width;
      const calcHeight = state.config.height;

      if (state.config.frameType === "vstavnaya") {
        const cost = computeCostVstavnaya(
          calcWidth,
          calcHeight,
          state.config.color,
          state.config.type,
          pricingStore.pricing ?? undefined,
          marginConfig,
        );
        const base = costToClientPrice(
          cost,
          pricingStore.pricing ?? undefined,
          marginConfig,
        );
        return isMetal
          ? base -
              costToClientPrice(
                PRICING_CONFIG.fixed.handles,
                pricingStore.pricing ?? undefined,
                marginConfig,
              )
          : base;
      }
      const cost = computeCost(
        calcWidth,
        calcHeight,
        state.config.color,
        state.config.type,
        pricingStore.pricing ?? undefined,
        marginConfig,
      );
      const base = costToClientPrice(
        cost,
        pricingStore.pricing ?? undefined,
        marginConfig,
      );
      return isMetal
        ? base -
            costToClientPrice(
              PRICING_CONFIG.fixed.handles,
              pricingStore.pricing ?? undefined,
              marginConfig,
            )
        : base;
    },
    /** Итоговая цена заказа для клиента (сетки + доп. услуги) */
    totalPrice(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const itemsTotal = state.items.reduce((sum, item) => sum + item.price, 0);

      const measurementAdd = state.measurementSelected
        ? this.measurementPriceCalculated
        : 0;

      // Доставка в итог только если в заказе есть сетки без монтажа (когда способ получения показывается)
      const needsDelivery = state.items.some(
        (item) => !item.typeName.includes(" + МОНТАЖ"),
      );
      const deliveryAdd =
        needsDelivery && state.delivery === "Доставка"
          ? this.deliveryPriceCalculated
          : 0;

      // Базовая сумма заказа (сетки + доставка + замер)
      const baseTotal = itemsTotal + deliveryAdd + measurementAdd;

      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;

      // Срочность считается от итоговой суммы (сетки + доставка + замер)
      const urgentFactor =
        marginConfig?.urgent_margin_percent !== null &&
        marginConfig?.urgent_margin_percent !== undefined
          ? marginConfig.urgent_margin_percent
          : (pricingStore.pricing?.markup.urgent_profit_factor ?? 10);
      const urgentAdd =
        state.discountType === "srochnyi"
          ? Math.max(
              Math.round((baseTotal * (urgentFactor / 100)) / 50) * 50,
              400,
            )
          : 0;

      if (import.meta.server) {
        if (pricingStore.pricing?.markup) {
          pricingStore.pricing.markup.urgent_profit_factor = urgentFactor;
          pricingStore.pricing.markup.delivery_profit_factor =
            marginConfig?.delivery_margin_percent !== null &&
            marginConfig?.delivery_margin_percent !== undefined
              ? marginConfig.delivery_margin_percent
              : (pricingStore.pricing.markup.delivery_profit_factor ?? 33);
          pricingStore.pricing.markup.installation_profit_factor =
            marginConfig?.installation_margin_percent !== null &&
            marginConfig?.installation_margin_percent !== undefined
              ? marginConfig.installation_margin_percent
              : (pricingStore.pricing.markup.installation_profit_factor ?? 33);
          pricingStore.pricing.markup.measurement_profit_factor =
            marginConfig?.measurement_margin_percent !== null &&
            marginConfig?.measurement_margin_percent !== undefined
              ? marginConfig.measurement_margin_percent
              : (pricingStore.pricing.markup.measurement_profit_factor ?? 5);
        }
      }

      const total = baseTotal + (urgentAdd || 0);
      return isNaN(total) ? 0 : total;
    },
    /** Доплата за монтаж за 1 шт: база из админки × (1 + коэффициент монтажа), округление до 50. Без принудительного минимума. */
    extrasInstallation(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      if (!pricingStore.pricing) return PRICING_CONFIG.extras.installation;

      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;

      const isVstavnaya = state.config.frameType === "vstavnaya";
      const basePrice = isVstavnaya
        ? (pricingStore.pricing.services.find(
            (s: any) => s.id === "installation_vsn",
          )?.price ?? 100)
        : (pricingStore.pricing.services.find(
            (s: any) => s.id === "installation",
          )?.price ?? 400);
      const factor =
        (marginConfig?.installation_margin_percent !== null &&
        marginConfig?.installation_margin_percent !== undefined
          ? marginConfig.installation_margin_percent
          : (pricingStore.pricing.markup.installation_profit_factor ?? 33)) /
        100;
      return roundTo(basePrice + basePrice * factor, 50);
    },
    /** Доплата за металл. ручки (8₽×2 шт из админки). В калькуляторе для клиента округление 50, для дилера 10. */
    extrasHandleMetal(): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const p = pricingStore.pricing;
      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;
      const cost = p
        ? (p.components.find((c: any) => c.id === "handle_metal")?.price ?? 8) *
          2
        : 16;
      return costToClientPrice(cost, p ?? undefined, marginConfig);
    },
    /** Покраска по RAL (100 ₽/м.п.) для текущей позиции — выводить отдельно и вычитать из прибыли. 0, если цвет не RAL. */
    currentRalPaintingAmount(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;
      return getRalPaintingAmount(
        state.config.width,
        state.config.height,
        state.config.color,
        pricingStore.pricing ?? undefined,
        marginConfig,
      );
    },
    /** Сумма покраски RAL по всем позициям в корзине (позиции с цветом RAL). */
    totalRalPaintingAmount(state): number {
      const pricingStore = usePricingStore();
      const tenantStore = useTenantStore();
      const marginConfig = (tenantStore.config as any)
        .margin_config as MarginConfig;
      return state.items
        .filter((item) => item.color === "RAL")
        .reduce(
          (sum, item) =>
            sum +
            getRalPaintingAmount(
              item.width,
              item.height,
              4,
              pricingStore.pricing ?? undefined,
              marginConfig,
            ),
          0,
        );
    },
  },
  actions: {
    addToOrder() {
      const base = this.currentPrice;
      const installation = this.config.installation
        ? this.extrasInstallation
        : 0;
      const metal =
        this.config.handleType === "metal" ? this.extrasHandleMetal : 0;
      const price = (base + installation + metal) * this.config.count;

      const colorName = COLOR_NAMES[this.config.color];
      const handleName = this.config.handleType === "metal" ? "МЕТАЛЛ" : "ПВХ";
      const frameName = FRAME_TYPE_NAMES[this.config.frameType];

      // Размеры в config уже скорректированы, берем их напрямую
      const finalWidth = this.config.width;
      const finalHeight = this.config.height;
      let methodLabel = "";

      if (this.config.measurementMethod === "stvorka") {
        methodLabel = "ПО СТВОРКЕ (-5/5 мм)";
      } else if (this.config.measurementMethod === "proem") {
        const isVstavnaya = this.config.frameType === "vstavnaya";
        const wCorr = isVstavnaya ? 17 : 50;
        const hCorr = isVstavnaya ? 12 : 50;
        methodLabel = `ПО ПРОЕМУ (+${wCorr}/${hCorr} мм)`;
      } else {
        methodLabel = "ПО СЕТКЕ";
      }

      this.items.push({
        id: Date.now(),
        type: this.config.type,
        typeName: `${MESH_TYPE_NAMES[this.config.type]} (${handleName})${this.config.installation ? " + МОНТАЖ" : ""}`,
        frameTypeName: frameName,
        color: colorName,
        width: finalWidth,
        height: finalHeight,
        count: this.config.count,
        price,
        measurementMethod: methodLabel,
      });
    },
    removeItem(id: number) {
      this.items = this.items.filter((item) => item.id !== id);
    },
    clearOrder() {
      this.items = [];
      this.delivery = "";
      this.deliveryPrice = 0;
      this.measurementSelected = false;
      this.measurementPrice = 0;
      this.discountType = "";
    },
    updateConfig(newConfig: Partial<typeof this.config>) {
      this.config = { ...this.config, ...newConfig };
    },
    updateItemCount(id: number, count: number) {
      const item = this.items.find((i) => i.id === id);
      if (item) {
        const unitPrice = item.price / item.count;
        item.count = Math.max(1, count);
        item.price = unitPrice * item.count;
      }
    },
    setMeasurementMethod(method: "stvorka" | "proem" | "old_mesh" | "") {
      const oldMethod = this.config.measurementMethod;
      if (oldMethod === method) return;

      // Если новый метод пустой (сброс), просто сохраняем и выходим
      if (method === "") {
        this.config.measurementMethod = "";
        return;
      }

      // 1. Сначала возвращаемся к "чистому" замеру (отменяем предыдущую корректировку)
      if (oldMethod === "stvorka") {
        this.config.width += 5;
        this.config.height += 5;
      } else if (oldMethod === "proem") {
        const isVstavnaya = this.config.frameType === "vstavnaya";
        const wCorr = isVstavnaya ? 17 : 50;
        const hCorr = isVstavnaya ? 12 : 50;
        this.config.width -= wCorr;
        this.config.height -= hCorr;
      }

      // 2. Применяем новую корректировку к текущим значениям
      if (method === "stvorka") {
        this.config.width -= 5;
        this.config.height -= 5;
      } else if (method === "proem") {
        const isVstavnaya = this.config.frameType === "vstavnaya";
        const wCorr = isVstavnaya ? 17 : 50;
        const hCorr = isVstavnaya ? 12 : 50;
        this.config.width += wCorr;
        this.config.height += hCorr;
      }

      // 3. Сохраняем новый метод
      this.config.measurementMethod = method;
    },
    setDelivery(value: string, price: number) {
      this.delivery = value;
      this.deliveryPrice = price;
    },
    setMeasurement(selected: boolean, price: number = 0) {
      this.measurementSelected = selected;
      this.measurementPrice = price;
    },
    setDiscount(type: "" | "srochnyi") {
      this.discountType = type;
    },
  },
});
