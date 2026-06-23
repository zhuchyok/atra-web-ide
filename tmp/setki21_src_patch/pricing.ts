// services/pricing.ts - Сервис ценообразования
// Извлечённая бизнес-логика из stores/order.ts

import { PRICING_CONFIG } from "~/constants/pricing";
import type { ColorId, MeshType, FrameType } from "~/types/mesh";
import type { GlobalPricing } from "~/stores/pricing";

export interface MarginConfig {
  category_coefficients?: Partial<
    Record<MeshType, { dealer?: number; client?: number }>
  >;
  base_margin_percent: number;
  city_multiplier: number;
  branch_multiplier: number;
  urgent_margin_percent?: number | null;
  delivery_margin_percent?: number | null;
  installation_margin_percent?: number | null;
  measurement_margin_percent?: number | null;
}

function comp(pricing: GlobalPricing, id: string, fallback: number): number {
  return pricing.components.find((c) => c.id === id)?.price ?? fallback;
}

/** Получить актуальный конфиг (из стора или дефолтный). Все цены из админки. */
export function getConfig(
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
  selectedMeshType?: MeshType,
) {
  if (!pricing) {
    const fallbackClientCoeff = selectedMeshType
      ? marginConfig?.category_coefficients?.[selectedMeshType]?.client
      : undefined;
    if (!fallbackClientCoeff) return PRICING_CONFIG;
    return {
      ...PRICING_CONFIG,
      markup: {
        ...PRICING_CONFIG.markup,
        clientFactorFromCost: fallbackClientCoeff,
      },
    };
  }

  const handlePlastic = comp(pricing, "handle_plastic", 2.2);
  const handleMetalPerPiece = comp(pricing, "handle_metal", 8);
  const mountFrame = comp(pricing, "mount_frame", 8);
  const mountVsn = comp(pricing, "mount_vsn", 30);
  const mountImpost = comp(pricing, "mount_impost", 1.8);
  const screwPrice = comp(pricing, "screw", 1);
  const rivetPrice = comp(pricing, "rivet", 5);
  const stretchPrice = comp(pricing, "stretch", 24);

  // Категорийные коэффициенты (на уровне дилера имеют приоритет, затем глобальные).
  const dealerCategoryCoeff = selectedMeshType
    ? marginConfig?.category_coefficients?.[selectedMeshType]
    : undefined;
  const globalCategoryCoeff = selectedMeshType
    ? (pricing.markup as any)?.category_coefficients?.[selectedMeshType]
    : undefined;
  const clientCoefficient =
    dealerCategoryCoeff?.client ??
    globalCategoryCoeff?.client ??
    pricing.markup.client;
  const finalClientFactor = clientCoefficient;
  if (import.meta.server && selectedMeshType) {
    console.error(
      `[PRICE_DEBUG] mesh=${selectedMeshType} dealerCoeff=${dealerCategoryCoeff?.dealer} clientCoeff=${dealerCategoryCoeff?.client} globalClient=${globalCategoryCoeff?.client} usedClientFactor=${finalClientFactor}`,
    );
  }

  return {
    ...PRICING_CONFIG,
    fixed: {
      ...PRICING_CONFIG.fixed,
      handles: handlePlastic * 2 /* 2,2₽ × 2 шт */,
      handlesMetalCost: handleMetalPerPiece * 2 /* 8₽ × 2 шт */,
      stretch: stretchPrice,
      workBase: pricing.markup.manufacturing_base,
      workPercent: pricing.markup.manufacturing_percent / 100,
    },
    variable: {
      ...PRICING_CONFIG.variable,
      meshPerM2: {
        standart: pricing.mesh.find((m) => m.id === "standart")?.price ?? 63,
        antimoshka:
          pricing.mesh.find((m) => m.id === "antimoshka")?.price ?? 265,
        ultravyu: pricing.mesh.find((m) => m.id === "ultravyu")?.price ?? 295,
        antikoshka:
          pricing.mesh.find((m) => m.id === "antikoshka")?.price ?? 414,
        antipyl: pricing.mesh.find((m) => m.id === "antipyl")?.price ?? 645,
      },
      profilePerMeter: {
        1: pricing.profiles.find((p) => p.id === "white")?.price ?? 60,
        2: pricing.profiles.find((p) => p.id === "brown")?.price ?? 64.8,
        3: pricing.profiles.find((p) => p.id === "anthracite")?.price ?? 70,
        4: pricing.profiles.find((p) => p.id === "ral")?.price ?? 60,
      },
      profilePerMeterVstavnaya: {
        1: pricing.profiles.find((p) => p.id === "white_vsn")?.price ?? 151,
        2: pricing.profiles.find((p) => p.id === "brown_vsn")?.price ?? 153,
        3:
          pricing.profiles.find((p) => p.id === "anthracite_vsn")?.price ?? 163,
        4: pricing.profiles.find((p) => p.id === "ral_vsn")?.price ?? 251,
      },
      impostPerMeter: {
        1: pricing.profiles.find((p) => p.id === "impost_white")?.price ?? 62,
        2: pricing.profiles.find((p) => p.id === "impost_brown")?.price ?? 67.2,
        3:
          pricing.profiles.find((p) => p.id === "impost_anthracite")?.price ??
          75,
        4: pricing.profiles.find((p) => p.id === "impost_white")?.price ?? 62,
      },
      ralPaintingPerMeter:
        pricing.profiles.find((p) => p.id === "ral_painting")?.price ?? 100,
      cordPerMeter:
        pricing.components.find((c) => c.id === "cord")?.price ?? 4.6,
    },
    markup: {
      ...PRICING_CONFIG.markup,
      dealerFactor: pricing.markup.dealer,
      clientFactorFromCost: finalClientFactor,
      measurementBase: pricing.markup.measurement_base,
      measurementPercent: (pricing.markup.measurement_percent ?? 5) / 100,
      measurementProfitFactor:
        (marginConfig?.measurement_margin_percent !== null &&
        marginConfig?.measurement_margin_percent !== undefined
          ? marginConfig.measurement_margin_percent
          : (pricing.markup.measurement_profit_factor ?? 5)) / 100,
      urgentProfitFactor:
        (marginConfig?.urgent_margin_percent !== null &&
        marginConfig?.urgent_margin_percent !== undefined
          ? marginConfig.urgent_margin_percent
          : pricing.markup.urgent_profit_factor) / 100,
      installationProfitFactor:
        (marginConfig?.installation_margin_percent !== null &&
        marginConfig?.installation_margin_percent !== undefined
          ? marginConfig.installation_margin_percent
          : pricing.markup.installation_profit_factor) / 100,
      deliveryProfitFactor:
        (marginConfig?.delivery_margin_percent !== null &&
        marginConfig?.delivery_margin_percent !== undefined
          ? marginConfig.delivery_margin_percent
          : pricing.markup.delivery_profit_factor) / 100,
    },
    fixedRamochnaya: {
      ...PRICING_CONFIG.fixedRamochnaya,
      cornersByColor: {
        1: comp(pricing, "corner_white", 3.75),
        2: comp(pricing, "corner_brown", 6),
        3: comp(pricing, "corner_anthracite", 7),
        4: comp(pricing, "corner_anthracite", 7),
      },
      mountPerPiece: mountFrame,
      screwCount: 12,
      screwPrice,
    },
    fixedVstavnaya: {
      ...PRICING_CONFIG.fixedVstavnaya,
      cornersByColor: {
        1: comp(pricing, "corner_vsn_white", 14.8),
        2: comp(pricing, "corner_vsn_brown", 4.85),
        3: comp(pricing, "corner_vsn_anthracite", 7.15),
        4: comp(pricing, "corner_vsn_anthracite", 7.15),
      },
      mountPerPiece: mountVsn,
      screwCount: 2,
      rivetCount: 2,
      screwPrice,
      rivetPrice,
      impostMountPrice: mountImpost,
    },
    extras: {
      installation:
        pricing.services.find((s) => s.id === "installation")?.price ?? 400,
      installationVsn:
        pricing.services.find((s) => s.id === "installation_vsn")?.price ?? 100,
      delivery: pricing.services.find((s) => s.id === "delivery")?.price ?? 300,
      deliveryMixed:
        pricing.services.find((s) => s.id === "delivery_mixed")?.price ?? 100,
      handleMetalCost: handleMetalPerPiece * 2,
      handleMetal: roundTo(
        handleMetalPerPiece * 2 * pricing.markup.client,
        50,
      ) /* клиент: округление 50 */,
    },
  };
}

/** Работа: база + 5% от всех материалов (себестоимость без учета работы). */
export function getWork(
  widthMm: number,
  heightMm: number,
  colorId: ColorId,
  meshType: MeshType,
  frameType: FrameType,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const f = config.fixed;

  // Рассчитываем себестоимость материалов (без учета самой работы)
  let materialCost = 0;

  const w = widthMm / 1000;
  const h = heightMm / 1000;
  const perimeterM = 2 * (w + h);
  const areaM2 = w * h;
  const v = config.variable ?? PRICING_CONFIG.variable;
  const areaCalc = Math.max(areaM2, v.minAreaM2);
  const meshPerM2 = v?.meshPerM2 ??
    (PRICING_CONFIG as any).meshPerM2 ?? {
      standart: 63,
      antimoshka: 265,
      ultravyu: 295,
      antikoshka: 414,
      antipyl: 645,
    };

  // 1. Полотно
  const meshBase = meshPerM2?.[meshType] ?? meshPerM2?.standart ?? 63;
  materialCost += areaCalc * meshBase * v.marginMesh;

  // 2. Профиль
  const profileLengthM = Math.max(0, perimeterM - 0.24);
  if (frameType === "vstavnaya") {
    materialCost +=
      profileLengthM *
      getProfilePerMeterVstavnaya(colorId, pricing, marginConfig);
  } else {
    materialCost +=
      profileLengthM *
      getProfilePerMeter(colorId, pricing, marginConfig) *
      v.marginProfile;
  }

  // 3. Шнур
  materialCost += perimeterM * v.cordPerMeter * v.marginCord;

  // 4. Импост
  const impostLengthM = Math.max(0, (widthMm - 48) / 1000);
  materialCost +=
    impostLengthM *
    getImpostPerMeter(colorId, pricing, marginConfig) *
    v.marginProfile;

  // 5. Фиксированные комплектующие: уголки 4 шт, ручки ПВХ 2×2,2, крепления, импост 1,8×2, саморезы/клепки, стрейч
  if (frameType === "vstavnaya") {
    const fv = config.fixedVstavnaya;
    const cornerPerPiece =
      (fv.cornersByColor as Record<number, number>)[colorId] ?? 14.8;
    materialCost += 4 * cornerPerPiece;
    materialCost += (fv.mountCount ?? 4) * (fv.mountPerPiece ?? 30); // 30₽×4
    materialCost += (fv.impostMountCount ?? 2) * (fv.impostMountPrice ?? 1.8);
    materialCost += (fv.screwCount ?? 2) * (fv.screwPrice ?? 1);
    materialCost += (fv.rivetCount ?? 2) * (fv.rivetPrice ?? 5);
    materialCost += config.fixed.handles;
    materialCost += f.stretch;
  } else {
    const fr = config.fixedRamochnaya;
    const cornerPerPiece =
      (fr.cornersByColor as Record<number, number>)[colorId] ?? 3.75;
    materialCost += 4 * cornerPerPiece;
    materialCost += (fr.mountCount ?? 4) * (fr.mountPerPiece ?? 8); // 8₽×4
    materialCost += (fr.screwCount ?? 12) * (fr.screwPrice ?? 1);
    materialCost += (fr.impostMountCount ?? 2) * (fr.impostMountPrice ?? 1.8);
    materialCost += config.fixed.handles;
    materialCost += f.stretch;
  }

  // Формула: база + % от всех материалов
  return f.workBase + materialCost * f.workPercent;
}

/** Фикса рамочной: 4×уголок + ручки 2×2,2 + крепления 8₽×4 + саморезы 12 шт + импост 1,8₽×2 + стрейч + работа. */
function getFixedTotal(
  widthMm: number,
  heightMm: number,
  colorId: number,
  meshType: string,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const f = config.fixed;
  const fr = config.fixedRamochnaya;
  const cornersTotal =
    4 * ((fr.cornersByColor as Record<number, number>)[colorId] ?? 3.75);
  const mountsTotal = (fr.mountCount ?? 4) * (fr.mountPerPiece ?? 8);
  const screwsTotal = (fr.screwCount ?? 12) * (fr.screwPrice ?? 1);
  const impostMountTotal =
    (fr.impostMountCount ?? 2) * (fr.impostMountPrice ?? 1.8);
  const work = getWork(
    widthMm,
    heightMm,
    colorId as ColorId,
    meshType as MeshType,
    "standart",
    pricing,
    marginConfig,
  );
  return (
    cornersTotal +
    f.handles +
    mountsTotal +
    screwsTotal +
    impostMountTotal +
    f.stretch +
    work
  );
}

/** Фикса вставной VSN: 4×уголок + ручки 2×2,2 + крепления 30₽×4 + саморезы 2 шт + клепки 2 шт + импост 1,8₽×2 + стрейч + работа. */
function getFixedTotalVstavnaya(
  widthMm: number,
  heightMm: number,
  colorId: number,
  meshType: string,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const f = config.fixed;
  const fv = config.fixedVstavnaya;
  const cornersTotal =
    4 * ((fv.cornersByColor as Record<number, number>)[colorId] ?? 14.8);
  const mountsTotal = (fv.mountCount ?? 4) * (fv.mountPerPiece ?? 30);
  const screwsTotal = (fv.screwCount ?? 2) * (fv.screwPrice ?? 1);
  const rivetsTotal = (fv.rivetCount ?? 2) * (fv.rivetPrice ?? 5);
  const impostMountTotal =
    (fv.impostMountCount ?? 2) * (fv.impostMountPrice ?? 1.8);
  const work = getWork(
    widthMm,
    heightMm,
    colorId as ColorId,
    meshType as MeshType,
    "vstavnaya",
    pricing,
    marginConfig,
  );
  return (
    cornersTotal +
    f.handles +
    mountsTotal +
    screwsTotal +
    rivetsTotal +
    impostMountTotal +
    f.stretch +
    work
  );
}

/** Цена профиля за м.п. по цвету (RAL = база + наценка покраски). */
function getProfilePerMeter(
  colorId: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const v = config.variable;
  const base = (v.profilePerMeter as Record<number, number>)[colorId] ?? 60;
  if (colorId === 4) return base + v.ralPaintingPerMeter;
  return base;
}

/** Цена поперечины (импост) за м.п. по цвету (RAL = база + наценка покраски). */
function getImpostPerMeter(
  colorId: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const v = config.variable;
  const base = (v.impostPerMeter as Record<number, number>)[colorId] ?? 62;
  if (colorId === 4) return base + v.ralPaintingPerMeter;
  return base;
}

/** Профиль вставной VSN за м.п. по цвету (151/153/163/401), с запасом 10%. */
function getProfilePerMeterVstavnaya(
  colorId: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const v = config.variable;
  const pv = (v.profilePerMeterVstavnaya as Record<number, number>) ?? {
    1: 151,
    2: 153,
    3: 163,
    4: 251,
  };
  const profile = pv[colorId] ?? pv[1];
  return profile * v.marginProfile;
}

/**
 * Себестоимость S для рамочной сетки (без доп. монтажа/металл).
 * Профиль: (периметр − 240 мм) × цена/м.п. × 1,1. Шнур: периметр × 4,6 × 1,01. Импост: (ширина − 48 мм) × цена/м.п. × 1,1. Полотно: площадь × цена/м² × 1,26.
 */
export function computeCost(
  widthMm: number,
  heightMm: number,
  colorId: ColorId,
  meshType: MeshType,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const w = widthMm / 1000;
  const h = heightMm / 1000;
  const perimeterM = 2 * (w + h);
  const areaM2 = w * h;
  const areaCalc = Math.max(areaM2, config.variable.minAreaM2);

  const v = config.variable ?? PRICING_CONFIG.variable;
  const meshPerM2 = v?.meshPerM2 ??
    (PRICING_CONFIG as any).meshPerM2 ?? {
      standart: 63,
      antimoshka: 265,
      ultravyu: 295,
      antikoshka: 414,
      antipyl: 645,
    };
  const meshBase = meshPerM2?.[meshType] ?? meshPerM2?.standart ?? 63;
  const meshCost = areaCalc * meshBase * v.marginMesh;

  const fixedTotal = getFixedTotal(
    widthMm,
    heightMm,
    colorId,
    meshType,
    pricing,
    marginConfig,
  );
  const profileLengthM = Math.max(0, perimeterM - 0.24);
  const profileCost =
    profileLengthM *
    getProfilePerMeter(colorId, pricing, marginConfig) *
    v.marginProfile;
  const cordCost = perimeterM * v.cordPerMeter * v.marginCord;
  const impostLengthM = Math.max(0, (widthMm - 48) / 1000);
  const impostCost =
    impostLengthM *
    getImpostPerMeter(colorId, pricing, marginConfig) *
    v.marginProfile;

  return fixedTotal + profileCost + cordCost + impostCost + meshCost;
}

/**
 * Себестоимость S для вставной VSN: та же схема — профиль (периметр−240), шнур, импост (ширина−48), полотно (площадь×1,26).
 */
export function computeCostVstavnaya(
  widthMm: number,
  heightMm: number,
  colorId: ColorId,
  meshType: MeshType,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const w = widthMm / 1000;
  const h = heightMm / 1000;
  const perimeterM = 2 * (w + h);
  const areaM2 = w * h;
  const areaCalc = Math.max(areaM2, config.variable.minAreaM2);

  const v = config.variable ?? PRICING_CONFIG.variable;
  const meshPerM2 = v?.meshPerM2 ??
    (PRICING_CONFIG as any).meshPerM2 ?? {
      standart: 63,
      antimoshka: 265,
      ultravyu: 295,
      antikoshka: 414,
      antipyl: 645,
    };
  const meshBase = meshPerM2?.[meshType] ?? meshPerM2?.standart ?? 63;
  const meshCost = areaCalc * meshBase * v.marginMesh;

  const fixedTotal = getFixedTotalVstavnaya(
    widthMm,
    heightMm,
    colorId,
    meshType,
    pricing,
    marginConfig,
  );
  const profileLengthM = Math.max(0, perimeterM - 0.24);
  const profileCost =
    profileLengthM *
    getProfilePerMeterVstavnaya(colorId, pricing, marginConfig);
  const cordCost = perimeterM * v.cordPerMeter * v.marginCord;
  const impostLengthM = Math.max(0, (widthMm - 48) / 1000);
  const impostCost =
    impostLengthM *
    getImpostPerMeter(colorId, pricing, marginConfig) *
    v.marginProfile;

  return fixedTotal + profileCost + cordCost + impostCost + meshCost;
}

/** Округление до шага (50 или 10) */
export function roundTo(value: number, step: number): number {
  return Math.round(value / step) * step;
}

/** Цена для клиента: считается отдельно от себестоимости (не от дилера). */
export function costToClientPrice(
  cost: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
  meshType?: MeshType,
): number {
  const config = getConfig(pricing, marginConfig, meshType);
  const { clientFactorFromCost, clientOffsetFromCost, clientRound } =
    config.markup;
  const clientPrice = cost * clientFactorFromCost + clientOffsetFromCost;
  return Math.max(0, roundTo(clientPrice, clientRound));
}

/** Цена для дилера */
export function costToDealerPrice(
  cost: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const { dealerFactor, dealerOffset, dealerRound } = config.markup;
  const dealerPrice = cost * dealerFactor + dealerOffset;
  return Math.max(0, roundTo(dealerPrice, dealerRound));
}

/** Потеря на оплату картой от суммы заказа (руб). */
export function getCardFee(
  revenue: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const p = config.fees?.cardPercent ?? 0.025;
  return revenue * p;
}

/** Выручка после вычета комиссии карты (руб). */
export function getNetRevenueAfterCard(
  revenue: number,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig);
  const p = config.fees?.cardPercent ?? 0.025;
  return revenue * (1 - p);
}

/** Сумма покраски по RAL (100 ₽/м.п.): профиль + импост. Только для colorId === 4 (RAL). Выводится отдельно и вычитается из прибыли. */
export function getRalPaintingAmount(
  widthMm: number,
  heightMm: number,
  colorId: ColorId,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  if (colorId !== 4) return 0;
  const config = getConfig(pricing, marginConfig);
  const perimeterM = 2 * (widthMm / 1000 + heightMm / 1000);
  const profileLengthM = Math.max(0, perimeterM - 0.24);
  const impostLengthM = Math.max(0, (widthMm - 48) / 1000);
  const ralPerMeter = config.variable.ralPaintingPerMeter ?? 100;
  return (profileLengthM + impostLengthM) * ralPerMeter;
}

/** Прибыль от заказа: выручка после карты − себестоимость − покраска RAL (если есть). */
export function getOrderProfit(
  revenue: number,
  cost: number,
  ralAmount: number = 0,
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  return (
    getNetRevenueAfterCard(revenue, pricing, marginConfig) - cost - ralAmount
  );
}

/** Размер ячейки сетки в зависимости от типа полотна (меньше число — мельче ячейка) */
export function getMeshSize(meshType: MeshType): number {
  switch (meshType) {
    case "antimoshka":
      return 3; // мельче стандарта: мелкая ячейка 0.8x0.8
    case "ultravyu":
      return 3; // мельче стандарта: повышенная прозрачность, мелкая ячейка
    case "antipyl":
      return 3; // мелкая ячейка
    case "antikoshka":
      return 5; // крупная ячейка Pet Screen
    default:
      return 4; // стандартная 1.2x1.2
  }
}

/** Толщина нити сетки */
export function getMeshThickness(meshType: MeshType): string {
  return meshType === "antikoshka" ? "2px" : "1px";
}

/** Рассчитать полную цену для позиции */
export function calculateItemPrice(
  widthMm: number,
  heightMm: number,
  colorId: ColorId,
  meshType: MeshType,
  frameType: FrameType,
  count: number = 1,
  hasInstallation: boolean = false,
  handleType: "pvc" | "metal" = "pvc",
  pricing?: GlobalPricing,
  marginConfig?: MarginConfig,
): number {
  const config = getConfig(pricing, marginConfig, meshType);
  const cost =
    frameType === "vstavnaya"
      ? computeCostVstavnaya(
          widthMm,
          heightMm,
          colorId,
          meshType,
          pricing,
          marginConfig,
        )
      : computeCost(
          widthMm,
          heightMm,
          colorId,
          meshType,
          pricing,
          marginConfig,
        );

  const base = costToClientPrice(cost, pricing, marginConfig, meshType);
  const installation = hasInstallation ? config.extras.installation : 0;
  const metal = handleType === "metal" ? config.extras.handleMetal : 0;

  // Если ручки металлические, вычитаем стоимость ПВХ ручек из базы, так как они уже в фиксе
  const finalBase =
    handleType === "metal"
      ? base -
        costToClientPrice(config.fixed.handles, pricing, marginConfig, meshType)
      : base;

  return (finalBase + installation + metal) * count;
}
