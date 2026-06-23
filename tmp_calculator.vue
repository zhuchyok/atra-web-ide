<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import ExtraServices from '~/components/calculator/ExtraServices.vue'
import ParameterSelectors from '~/components/calculator/ParameterSelectors.vue'
import QuickOptions from '~/components/calculator/QuickOptions.vue'
import Visualizer from '~/components/calculator/Visualizer.vue'
import { useAuthStore } from '~/stores/auth'
const auth = useAuthStore()
const store = useOrderStore()
const pricingStore = usePricingStore()
const tenant = useTenantStore()
const brandPrimary = computed(() => tenant.config.branding?.primary_color || '#2A6AB2')

const extraServicesOptions = [
  {
    id: 'windows',
    name: 'Окна и остекление',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-12 h-12">
      <path d="M3 3h18v18H3zM12 3v18M3 12h18M9 3v9M15 3v9M9 12v9M15 12v9" />
    </svg>`
  },
  {
    id: 'balcony',
    name: 'Отделка балконов',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-12 h-12">
      <path d="M3 11h18M3 15h18M3 19h18M5 11v8M9 11v8M13 11v8M17 11v8M19 11v8M3 7h18l-2-4H5z" />
    </svg>`
  },
  {
    id: 'ceilings',
    name: 'Натяжные потолки',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-12 h-12">
      <path d="M3 8l9-3 9 3v4l-9 3-9-3z" />
      <path d="M7 14l-1 3M12 16v3M17 14l1 3" />
      <path d="M12 2l1 1.5M4 6l1.5.5M20 6l-1.5.5" />
    </svg>`
  },
  {
    id: 'blinds',
    name: 'Жалюзи',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-12 h-12">
      <path d="M4 3h16M4 7h16M4 11h16M4 15h16M4 19h16M8 3v16" />
    </svg>`
  },
  {
    id: 'doors',
    name: 'Двери',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-12 h-12">
      <path d="M5 3h14v18H5zM15 12v.01" />
    </svg>`
  }
]

const THUMB_SIZE = 42
const DOT_SIZE = 13
const H_SLIDER_W = 210
const V_SLIDER_W = 280

const isDraggingWidth = ref(false)
const isDraggingHeight = ref(false)

const widthThumbCenter = computed(() => {
  const ratio = (store.config.width - 200) / (1500 - 200)
  return ratio * (H_SLIDER_W - THUMB_SIZE) + THUMB_SIZE / 2
})
const heightThumbCenter = computed(() => {
  const ratio = (store.config.height - 200) / (2000 - 200)
  return ratio * (V_SLIDER_W - THUMB_SIZE) + THUMB_SIZE / 2
})
const privacyPolicyUrl = computed(() => tenant.config?.legal?.privacy_policy_url?.trim() || '/privacy')

// По умолчанию при открытии калькулятора всегда выбрана доставка
onMounted(() => {
  store.setDelivery('Доставка', store.deliveryPriceCalculated)
})

// Обновляем цену доставки в сторе, когда загрузятся глобальные цены
watch(() => pricingStore.pricing, (newPricing) => {
  if (newPricing && store.delivery === 'Доставка') {
    store.setDelivery('Доставка', store.deliveryPriceCalculated)
  }
}, { immediate: true })

// Способ получения: обязателен, если в заказе есть сетки без монтажа (все без монтажа или смешанный заказ)
const deliveryRequired = computed(() => store.items.length > 0 && store.hasItemsWithoutInstallation)
const deliverySelected = computed(() => {
  if (!deliveryRequired.value) return true
  if (store.isMixedOrder) return true

  // Проверяем, что выбранный ID доставки есть в списке доступных опций
  return deliveries.value.some(d => d.id === store.delivery)
})
const canSubmitOrder = computed(() =>
  deliverySelected.value &&
  store.config.measurementMethod !== ''
)

// Количество выбранных дополнительных услуг (для бейджа у заголовка)
const extrasCount = computed(() => {
  let n = 0
  if (store.hasItemsWithoutInstallation || store.isMixedOrder) n += 1 // способ получения
  if (store.measurementSelected) n += 1
  if (store.allItemsWithInstallation && !store.isMixedOrder && store.discountType === 'srochnyi') n += 1
  return n
})

// При смешанном заказе (сетки с монтажом и без) — только доставка (смешанная), отменить нельзя
watch(
  () => store.isMixedOrder,
  (mixed) => {
    if (mixed) {
      store.setDelivery('Доставка', store.deliveryPriceCalculated)
    }
  }
)

// Состояние кнопки "Добавить в заказ"
const isAdded = ref(false)
const cancelHover = ref(false)
const orderBlockRef = ref<HTMLElement | null>(null)
const calculatorRef = ref<HTMLElement | null>(null)
const orderFormBlockRef = ref<HTMLElement | null>(null)

// Логика Мастера (Wizard)
const currentStep = ref(1)
const maxStep = 3

const nextStep = () => {
  if (currentStep.value < maxStep) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const scrollToCalculator = () => {
  currentStep.value = 1
  nextTick(() => {
    // Используем scrollIntoView на самом верхнем контейнере калькулятора
    calculatorRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

const handleAddToOrder = () => {
  store.addToOrder()
  isAdded.value = true

  // Сбрасываем калькулятор на первый шаг в фоне
  currentStep.value = 1

  // Скроллим только к списку заказа, чтобы пользователь видел результат
  nextTick(() => {
    orderBlockRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })

  setTimeout(() => {
    isAdded.value = false
  }, 1000)
}

const types = [
  { id: 'standart', name: 'СТАНДАРТ' },
  { id: 'antimoshka', name: 'АНТИМОШКА' },
  { id: 'antikoshka', name: 'АНТИКОШКА' },
  { id: 'ultravyu', name: 'УЛЬТРАВЬЮ' },
  { id: 'antipyl', name: 'АНТИПЫЛЬ' }
]

const frameTypes = [
  { id: 'standart', name: 'РАМОЧНАЯ' },
  { id: 'vstavnaya', name: 'ВСТАВНАЯ VSN' }
]

const colors = [
  { id: 1, name: 'БЕЛАЯ', hex: '#FFFFFF' },
  { id: 2, name: 'КОРИЧНЕВАЯ', hex: '#6F4E37' },
  { id: 3, name: 'АНТРАЦИТ', hex: '#555D61' },
  { id: 4, name: 'RAL', hex: '#2A6AB2' }
]

// Популярные цвета RAL для анимации кнопки
const ralAnimationColors = [
  '#2D572C', // RAL 6005 (Зеленый мох)
  '#1B3045', // RAL 5011 (Стальной синий)
  '#59191F', // RAL 3005 (Винно-красный)
  '#3E3C32', // RAL 8019 (Серо-коричневый)
  '#0A0A0A', // RAL 9005 (Черный)
  '#939176', // RAL 7034 (Желто-серый)
  '#5A6D76', // RAL 7031 (Сине-серый)
  '#D7D7D7', // RAL 7035 (Светло-серый)
  '#7096BB', // RAL 5024 (Пастельно-синий)
  '#493328', // RAL 8014 (Сепия)
  '#A5A8A6', // RAL 9006 (Серебристый)
  '#204A87', // RAL 5002 (Ультрамарин)
  '#F1753F'  // RAL 2004 (Оранжевый)
]

// ... (предыдущий код) ...
const currentRalIndex = ref(0)
const animatedRalColor = computed(() => ralAnimationColors[currentRalIndex.value])

// SEO: Микроразметка цен для поисковиков
useHead({
  script: [
    {
      type: 'application/ld+json',
      children: JSON.stringify({
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": `Москитные сетки в ${tenant.config.city || 'Чебоксарах'}`,
        "description": "Индивидуальный расчет стоимости москитных сеток: Антикошка, Антипыль, VSN. Изготовление от 1 дня.",
        "brand": {
          "@type": "Brand",
          "name": tenant.config.dealer_name || (tenant.config.city?.includes('Чебоксары') ? 'Сетки 21' : 'Сетки Москитки')
        },
        "offers": {
          "@type": "AggregateOffer",
          "lowPrice": "800",
          "highPrice": "5500",
          "priceCurrency": "RUB",
          "offerCount": "10",
          "availability": "https://schema.org/InStock",
          "areaServed": tenant.config.city || "Чебоксары, Новочебоксарск"
        }
      })
    }
  ]
})

onMounted(() => {
// ... (остальной код) ...
  store.setDelivery('Доставка', store.deliveryPriceCalculated)
  // Анимация смены цветов только для рамки, если выбран RAL
  setInterval(() => {
    currentRalIndex.value = (currentRalIndex.value + 1) % ralAnimationColors.length
  }, 500)
})

// Цвет рамки в визуализации
const frameColor = computed(() => {
  if (store.config.color === 4) return animatedRalColor.value
  const found = colors.find(c => c.id === store.config.color)
  return found ? found.hex : '#333333'
})

const selectType = (id: string, name: string) => {
  store.updateConfig({ type: id, typeName: name })
}

const selectFrameType = (id: string) => {
  store.updateConfig({ frameType: id })
  // Если выбрана вставная VSN и текущий метод замера "По створке", сбрасываем его
  if (id === 'vstavnaya' && store.config.measurementMethod === 'stvorka') {
    store.setMeasurementMethod('')
  }
}

const selectColor = (id: number) => {
  store.updateConfig({ color: id })
}

  const deliveries = computed(() => {
    const city = tenant.config.city || 'Чебоксары'
    const isChuvashia = city.includes('Чебоксары') || city.includes('Новочебоксарск')

    const options = []

    // Динамические пункты самовывоза из конфига (филиалы)
    if (tenant.config.contacts?.branches?.length) {
      tenant.config.contacts.branches.forEach(branch => {
        options.push({
          id: branch.id || branch.name,
          name: `Самовывоз ${branch.name} ${branch.address}`,
          price: 0,
          icon: 'building'
        })
      })
    } else {
      // Если филиалы не заполнены — используем город из основной админки (tenant.config.city)
      options.push({ id: 'Самовывоз', name: `Самовывоз ${city}`, price: 0, icon: 'building' })
    }

    // Доставка всегда доступна
    options.push({
      id: 'Доставка',
      name: isChuvashia ? 'Доставка Чебоксары и Новочебоксарск' : `Доставка ${city}`,
      price: store.deliveryPriceCalculated,
      icon: 'truck'
    })

    return options
  })

const urgentOrderOption = computed(() => {
  // Рассчитываем цену срочности для отображения в кнопке
  // В сторе она считается от итога, здесь для превью покажем примерную от текущей суммы
  const baseTotal = store.items.reduce((sum, item) => sum + item.price, 0) + (store.delivery === 'Доставка' ? store.deliveryPriceCalculated : 0) + (store.measurementSelected ? store.measurementPriceCalculated : 0)
  const factor = (pricingStore.pricing?.markup.urgent_profit_factor ?? 10) / 100
  const urgentPrice = Math.round((baseTotal * factor) / 50) * 50
  return {
    id: 'srochnyi' as const,
    name: 'Приоритетный срочный заказ',
    price: Math.max(urgentPrice, 400)
  }
})

const measurementOption = computed(() => {
  const city = tenant.config.city || 'Чебоксары'
  const isChuvashia = city.includes('Чебоксары') || city.includes('Новочебоксарск')
  const name = isChuvashia ? 'Замер Чебоксары и Новочебоксарск' : `Замер ${city}`

  return {
    id: 'measurement',
    name,
    price: store.measurementPriceCalculated
  }
})

// Размер ячейки сетки в зависимости от типа полотна (меньше число — мельче ячейка на превью)
const meshSize = computed(() => {
  switch (store.config.type) {
    case 'standart': return 4    // Стандартная 1.2x1.2
    case 'antimoshka': return 3 // Мельче стандарта: микро-ячейка 0.8x0.8
    case 'antikoshka': return 5  // Крупная ячейка Pet Screen
    case 'ultravyu': return 3 // Мельче стандарта: прозрачность + мелкая ячейка
    case 'antipyl': return 2     // Самая мелкая ячейка 0.8x0.8
    default: return 4
  }
})

// Толщина нити сетки и прозрачность
const meshThickness = computed(() => {
  switch (store.config.type) {
    case 'antikoshka': return '2px'   // Толстая нить (полиэстер)
    case 'ultravyu': return '0.65px'   // Тонкая нить, но линии видны на превью (не 0.4px — иначе сетка не видна)
    case 'antimoshka': return '0.7px' // Было 0.8, стало 0.7 (тонкая нить)
    case 'antipyl': return '0.8px'    // Было 0.7, стало 0.8 (тонкая нить)
    default: return '1px'             // Стандарт
  }
})

const meshOpacity = computed(() => {
  switch (store.config.type) {
    case 'ultravyu': return '0.2'     // Прозрачнее стандарта, но линии сетки видны на превью
    case 'antikoshka': return '0.45'  // Самая плотная и темная
    case 'antipyl': return '0.35'     // Плотная (фильтр)
    case 'antimoshka': return '0.28'  // Чуть плотнее стандарта
    default: return '0.22'            // Стандарт
  }
})

// Редактирование размеров вручную
const editingWidth = ref(false)
const editingHeight = ref(false)
const tempWidth = ref(350)
const tempHeight = ref(1000)

const startEditWidth = () => {
  tempWidth.value = store.config.width
  editingWidth.value = true
}

const startEditHeight = () => {
  tempHeight.value = store.config.height
  editingHeight.value = true
}

const saveWidth = () => {
  let val = parseInt(String(tempWidth.value)) || 350
  val = Math.max(200, Math.min(1500, val))
  store.updateConfig({ width: val })
  store.setMeasurementMethod('') // Сбрасываем метод замера при ручном изменении
  editingWidth.value = false
}

const saveHeight = () => {
  let val = parseInt(String(tempHeight.value)) || 1000
  val = Math.max(200, Math.min(2000, val))
  store.updateConfig({ height: val })
  store.setMeasurementMethod('') // Сбрасываем метод замера при ручном изменении
  editingHeight.value = false
}

const measurementMethods = [
  {
    id: 'stvorka',
    name: 'По створке окна',
    desc: 'ИЗМЕРИЛИ ВНУТРЕННЮЮ СТОРОНУ ЗАКРЫТОЙ СТВОРКИ. <br/>МЫ АВТОМАТИЧЕСКИ УМЕНЬШИЛИ РАЗМЕР НА 5 ММ ДЛЯ ПОЛУЧЕНИЯ ТОЧНЫХ ГАБАРИТОВ ГОТОВОГО ИЗДЕЛИЯ.',
    image: '/images/measure-stvorka.png'
  },
  {
    id: 'proem',
    name: 'По проему',
    desc: 'ИЗМЕРИЛИ ОТКРЫТЫЙ ПРОЕМ ОТ КРАЯ ДО КРАЯ РЕЗИНКИ. <br/>МЫ АВТОМАТИЧЕСКИ УВЕЛИЧИЛИ РАЗМЕР НА 50 ММ ДЛЯ ПОЛУЧЕНИЯ ГАБАРИТОВ ГОТОВОЙ СЕТКИ.',
    image: '/images/measure-proem.png'
  },
  {
    id: 'old_mesh',
    name: 'По старой сетке',
    desc: 'ВЫ УКАЗАЛИ ТОЧНЫЕ РАЗМЕРЫ ГОТОВОГО ИЗДЕЛИЯ. <br/>ИЗГОТОВИМ СЕТКУ СТРОГО ПО ЭТИМ ПАРАМЕТРАМ БЕЗ ДОПОЛНИТЕЛЬНЫХ КОРРЕКТИРОВОК.',
    image: '/images/measure-old.png'
  }
]

const selectMeasurementMethod = (id: 'stvorka' | 'proem' | 'old_mesh') => {
  store.setMeasurementMethod(id)
}

const showOrderForm = ref(false)
const form = reactive({
  name: '',
  phone: '',
  address: '',
  comment: '',
  agree: false,
  showExtras: false,
  extraServices: [] as string[]
})

const toggleExtraService = (id: string) => {
  const index = form.extraServices.indexOf(id)
  if (index === -1) {
    form.extraServices.push(id)
  } else {
    form.extraServices.splice(index, 1)
  }
}

/** Ошибки валидации по полям (отображаются под полем) */
const formErrors = reactive<Record<string, string>>({ name: '', phone: '', address: '', comment: '' })

/** Российские форматы: +7 (XXX) XX-XX-XX, +7 (XXXX) XX-XX-XX, +79XXXXXXXXX */
const PHONE_REGEX = /^\+7\s?\(\d{3,4}\)\s?\d{2,3}-\d{2}-\d{2}$|^\+7\d{10}$/

/** Допустимые символы в поле телефона: цифры, +, пробел, скобки, дефис. Не более 11 цифр (+7 и 10 цифр номера). */
const PHONE_ALLOWED = /[\d+\s()\-]/g
const MAX_PHONE_DIGITS = 11

/** Символы, которые можно вводить с клавиатуры (мировая практика: ограничить ввод до допустимых) */
const PHONE_KEY_ALLOWED = /^[\d+\s\-()]$/

/**
 * Форматирует ввод телефона в вид +7 (XXX) XXX-XX-XX (мировая практика: маска при вводе).
 * Только цифры, макс. 11; ведущая 8 заменяется на 7.
 */
function formatPhoneDisplay(raw: string): string {
  const digits = (raw.match(/\d/g) || []).join('').slice(0, MAX_PHONE_DIGITS)
  if (digits.length === 0) return ''
  let d = digits
  if (d.startsWith('8') && d.length <= 11) d = '7' + d.slice(1)
  else if (!d.startsWith('7')) d = '7' + d
  d = d.slice(0, 11)
  if (d.length <= 1) return d === '7' ? '+7' : '+7 (' + d
  if (d.length <= 4) return '+7 (' + d.slice(1)
  if (d.length <= 7) return '+7 (' + d.slice(1, 4) + ') ' + d.slice(4)
  if (d.length <= 9) return '+7 (' + d.slice(1, 4) + ') ' + d.slice(4, 7) + '-' + d.slice(7)
  return '+7 (' + d.slice(1, 4) + ') ' + d.slice(4, 7) + '-' + d.slice(7, 9) + '-' + d.slice(9, 11)
}

/** Оставляет только допустимые символы, обрезает до 11 цифр и форматирует отображение */
function sanitizePhoneInput(value: string): string {
  const allowed = (value.match(PHONE_ALLOWED) || []).join('')
  const digits = allowed.replace(/\D/g, '')
  if (digits.length === 0) return ''
  return formatPhoneDisplay(allowed)
}

/** Блокирует ввод букв и недопустимых символов (только цифры, +, пробел, скобки, дефис) */
function onPhoneKeydown(e: KeyboardEvent) {
  const key = e.key
  if (key.length === 1 && !PHONE_KEY_ALLOWED.test(key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault()
  }
}

function onPhoneInput(e: Event) {
  form.phone = sanitizePhoneInput((e.target as HTMLInputElement).value)
  formErrors.phone = ''
}

function validateOrderForm(): boolean {
  formErrors.name = ''
  formErrors.phone = ''
  formErrors.address = ''
  formErrors.comment = ''
  let valid = true
  const name = form.name.trim()
  const phone = form.phone.trim()
  const address = form.address.trim()

  if (!name) {
    formErrors.name = 'Введите имя'
    valid = false
  }
  if (!phone) {
    formErrors.phone = 'Введите телефон'
    valid = false
  } else if (!PHONE_REGEX.test(phone.replace(/\s/g, ''))) {
    formErrors.phone = 'Формат: +7 (XXX) XXX-XX-XX'
    valid = false
  }

  // Адрес обязателен, если выбрана доставка, замер или есть товары с монтажом
  const isAddressRequired = store.delivery === 'Доставка' || store.hasItemsWithInstallation || store.measurementSelected
  if (isAddressRequired && !address) {
    formErrors.address = 'Введите адрес для доставки или замера'
    valid = false
  }

  return valid
}

const notification = reactive({
  show: false,
  message: '',
  type: 'success' as 'success' | 'error'
})

const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
  notification.message = message
  notification.type = type
  notification.show = true
  setTimeout(() => {
    notification.show = false
  }, 5000)
}

const openOrderForm = () => {
  if (!canSubmitOrder.value) return
  showOrderForm.value = true
  nextTick(() => {
    orderFormBlockRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

const submitOrder = async () => {
  if (!form.agree) return
  if (!validateOrderForm()) return

  const branch = tenant.config.contacts?.branches?.find(b => b.id === store.delivery || b.name === store.delivery)
  const branchId = branch?.id || tenant.config.branch_id || undefined
  const deliveryOption = deliveries.value.find(d => d.id === store.delivery)

    const orderData = {
      formName: form.name.trim(),
      formPhone: form.phone.trim(),
      formAddress: form.address.trim(),
      formComment: form.comment.trim(),
      list_order: store.items.map(i => {
        const methodMap = { stvorka: 'По створке', proem: 'По проему', old_mesh: 'По старой сетке' };
        const methodStr = i.measurementMethod ? ` [Замер: ${methodMap[i.measurementMethod as keyof typeof methodMap] || i.measurementMethod}]` : '';
        return `${i.frameTypeName ? i.frameTypeName + ': ' : ''}${i.typeName} (${i.width}x${i.height}, ${i.color})${methodStr} - ${i.count}шт`;
      }).join('<br>'),
      total_price_value: store.totalPrice,
      total_order_value: store.allItemsWithInstallation ? 'Монтаж' : (deliveryOption?.name || store.delivery),
      extra_services: (form.extraServices && form.extraServices.length > 0)
        ? form.extraServices.map(id => extraServicesOptions.find(o => o.id === id)?.name).join(', ')
        : undefined,
      measurement: store.measurementSelected,
      delivery_price: (store.hasItemsWithoutInstallation && store.delivery === "Доставка") ? store.deliveryPriceCalculated : 0,
      measurement_price: store.measurementSelected ? store.measurementPriceCalculated : 0,
      installation_price: 0,
      discount_type: store.discountType || undefined,
      dealer_id: tenant.config.dealer_id || undefined,
      branch_id: branchId,
      dealer_email: tenant.config.contacts?.emails?.[0] || undefined,
      formDealerEmail: tenant.config.email || undefined,
      items: store.items.map(i => ({
        name: i.typeName,
        quantity: i.count,
        price: i.price / i.count,
        params: {
          width: i.width,
          height: i.height,
          color: i.color,
          color_id: i.color === 'КОРИЧНЕВАЯ' ? 2 : (i.color === 'АНТРАЦИТ' ? 3 : (i.color === 'RAL' ? 4 : 1)), handle_type: i.typeName.includes('(МЕТАЛЛ)') ? 'metal' : 'pvc', installation: i.typeName.includes('+ МОНТАЖ'),
          mesh_type: i.type,
          frame_type: i.frameTypeName,
          measurement_method: i.measurementMethod
        }
      }))
    }

    console.log('Submitting order with data:', JSON.stringify({
      dealer_id: orderData.dealer_id,
      dealer_email: orderData.dealer_email,
      formDealerEmail: orderData.formDealerEmail
    }))

    try {
      // Используем относительный путь без лишних слешей
      const response = await $fetch('/api_nuxt/orders', {
        method: 'POST',
        body: orderData
      })

    if (response.success) {
      // Track conversion in Google Analytics
      if (typeof window !== 'undefined' && (window as any).trackConversion) {
        (window as any).trackConversion('order_submitted', store.totalPrice)
      }

      // Track conversion in Yandex Metrika
      if (typeof window !== 'undefined' && (window as any).reachMetrikaGoal) {
        (window as any).reachMetrikaGoal('ORDER_SUBMITTED', { price: store.totalPrice })
      }

      showNotification('Спасибо за заказ! Мы свяжемся с вами в ближайшее время.')
      store.clearOrder()
      showOrderForm.value = false
      form.name = ''
      form.phone = ''
      form.address = ''
      form.comment = ''
      form.agree = false
    }
  } catch (e: any) {
    console.error('Ошибка отправки:', e)
    const errorMessage = e.data?.statusMessage || e.data?.message || e.message || 'Произошла ошибка при отправке. Позвоните нам по телефону.'
    showNotification(errorMessage, 'error')
  }
}
</script>

<template>
  <!-- Отступы: как в блоке «Ваш заказ» (p-10 md:p-16). Между блоками — тот же размер (space-y-10 md:space-y-16). -->
  <div ref="calculatorRef" class="container mx-auto px-4 space-y-10 md:space-y-16 scroll-mt-40">
    <!-- Калькулятор -->
    <div class="bg-white rounded-[3rem] shadow-2xl overflow-hidden flex flex-col lg:flex-row border border-gray-100 h-auto lg:min-h-[680px] lg:h-[740px]">
      <!-- Визуализация (Левая часть) -->
      <div class="lg:w-4/12 bg-gray-50/50 p-10 flex flex-col items-center justify-center relative border-r border-gray-100 h-full">
        <Visualizer
          v-model:width="store.config.width"
          v-model:height="store.config.height"
          v-model:isDraggingWidth="isDraggingWidth"
          v-model:isDraggingHeight="isDraggingHeight"
          v-model:tempWidth="tempWidth"
          v-model:tempHeight="tempHeight"
          :frameColor="frameColor"
          :brandPrimary="brandPrimary"
          :editingWidth="editingWidth"
          :editingHeight="editingHeight"
          :heightThumbCenter="heightThumbCenter"
          :widthThumbCenter="widthThumbCenter"
          :dotSize="DOT_SIZE"
          :thumbSize="THUMB_SIZE"
          :vSliderW="V_SLIDER_W"
          :hSliderW="H_SLIDER_W"
          :meshThickness="meshThickness"
          :meshSize="meshSize"
          :meshOpacity="meshOpacity"
          :frameType="store.config.frameType"
          @startEditWidth="startEditWidth"
          @startEditHeight="startEditHeight"
          @saveWidth="saveWidth"
          @saveHeight="saveHeight"
        />
      </div>

      <div class="lg:w-8/12 px-10 md:px-16 pt-12 pb-8 lg:pb-8 flex flex-col justify-start min-w-0 overflow-hidden">
        <div class="flex items-center gap-5 mb-8">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-2xl transform -rotate-3" :style="{ backgroundColor: brandPrimary, boxShadow: `0 25px 50px -12px ${brandPrimary}4D` }">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          </div>
          <div class="flex flex-col">
            <h2 class="text-4xl font-black text-brand-dark uppercase tracking-tighter leading-none">Расчет стоимости</h2>
            <p class="text-gray-500 font-bold uppercase text-[10px] tracking-[0.2em] mt-3">Металлические крепления в комплекте!</p>
            <div class="flex items-center gap-2 mt-4">
              <div v-for="s in maxStep" :key="s"
                   @click="currentStep = s"
                   :class="['h-1.5 rounded-full transition-all duration-500 cursor-pointer hover:opacity-70',
                            s === currentStep ? 'w-8 bg-brand-blue' : (s < currentStep ? 'w-4 bg-brand-blue/40' : 'w-4 bg-gray-100')]"
                   :title="'Перейти к шагу ' + s"></div>
              <span class="text-[10px] font-black text-gray-300 uppercase tracking-widest ml-2">Шаг {{ currentStep }} из {{ maxStep }}</span>
            </div>
          </div>
        </div>

        <div class="flex-1 w-full min-w-0 transition-all duration-500 ease-in-out overflow-y-auto overflow-x-hidden">
          <Transition name="fade-slide" mode="out-in">
            <div :key="currentStep" class="space-y-10 pb-4">
              <!-- Шаг 1: Конфигурация -->
              <div v-if="currentStep === 1" class="space-y-10 flex flex-col h-full">
                <ParameterSelectors
                  :types="types"
                  :frame-types="frameTypes"
                  :colors="colors"
                  :selected-type="store.config.type"
                  :selected-frame-type="store.config.frameType"
                  :selected-color="store.config.color"
                  :brand-primary="brandPrimary"
                  :is-admin-or-dealer="auth.isAdmin || auth.user?.role === 'dealer' || auth.user?.role === 'subdealer'"
                  @select-type="selectType"
                  @select-frame-type="selectFrameType"
                  @select-color="selectColor"
                />

                <!-- Ручки / Монтаж / Количество (Перенесено с Шага 2) -->
                <div class="flex-1 flex flex-col justify-center py-4">
                  <ClientOnly>
                    <QuickOptions
                      v-model:handle-type="store.config.handleType"
                      v-model:installation="store.config.installation"
                      v-model:count="store.config.count"
                      :brand-primary="brandPrimary"
                    />
                    <template #fallback>
                      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 sm:gap-8 md:gap-12 h-[120px]" style="width: 100%" aria-hidden="true">
                        <div class="flex flex-col items-center gap-2">
                          <div class="h-3 w-16 bg-gray-100 rounded animate-pulse" />
                          <div class="h-10 w-24 bg-gray-50 rounded-lg animate-pulse" />
                        </div>
                        <div class="flex flex-col items-center gap-2">
                          <div class="h-3 w-14 bg-gray-100 rounded animate-pulse" />
                          <div class="h-10 w-20 bg-gray-50 rounded-lg animate-pulse" />
                        </div>
                        <div class="flex flex-col items-center gap-2">
                          <div class="h-3 w-20 bg-gray-100 rounded animate-pulse" />
                          <div class="h-10 w-16 bg-gray-50 rounded-lg animate-pulse" />
                        </div>
                      </div>
                    </template>
                  </ClientOnly>
                </div>
              </div>

              <!-- Шаг 2: Метод замера -->
              <div v-if="currentStep === 2" class="space-y-10 pt-2">

                <!-- Метод замера -->
                <div class="w-full min-w-0">
                  <label class="block text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] mb-5">Как вы измеряли?</label>
                  <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 w-full max-w-[700px] mx-auto">
                    <template v-for="m in measurementMethods" :key="m.id">
                          <div v-if="!(store.config.frameType === 'vstavnaya' && m.id === 'stvorka')"
                               class="flex flex-col gap-3">
                            <!-- Картинка метода замера -->
                            <div class="aspect-square rounded-2xl overflow-hidden border-2 transition-all duration-300 bg-white relative flex items-center justify-center p-3"
                                 :style="{
                                   borderColor: store.config.measurementMethod === m.id ? brandPrimary : '#f3f4f6',
                                   boxShadow: store.config.measurementMethod === m.id ? `0 10px 20px -5px ${brandPrimary}33` : 'none'
                                 }">
                              <img :src="m.image" :alt="m.name"
                                   class="w-full h-full object-contain opacity-90 group-hover:opacity-100 transition-all duration-500 scale-100" />
                            </div>

                            <button @click="selectMeasurementMethod(m.id as any)"
                                    :class="[
                                      'h-10 px-2 rounded-2xl text-[10px] font-black transition-all border-2 uppercase tracking-widest text-center whitespace-nowrap flex items-center justify-center measurement-method-btn',
                                      store.config.measurementMethod === m.id
                                        ? 'text-white border-transparent shadow-xl transform -translate-y-0.5'
                                        : 'bg-white text-gray-400 border-gray-100'
                                    ]"
                                    :style="store.config.measurementMethod === m.id
                                      ? { backgroundColor: brandPrimary, boxShadow: `0 20px 25px -5px ${brandPrimary}33` }
                                      : { '--brand-primary': brandPrimary, color: store.config.measurementMethod === m.id ? 'white' : undefined, borderColor: store.config.measurementMethod === m.id ? 'transparent' : undefined }">
                              {{ m.name }}
                            </button>
                          </div>
                    </template>
                  </div>

                  <!-- Динамическая подсказка под кнопками -->
                  <div v-if="store.config.measurementMethod"
                       class="mt-5 p-5 rounded-2xl border animate-in fade-in slide-in-from-top-2 duration-300"
                       :style="{ borderColor: brandPrimary + '1A', backgroundColor: brandPrimary + '0D' }">
                    <div class="flex gap-4 items-start">
                      <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5" :style="{ backgroundColor: brandPrimary + '1A' }">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" :style="{ color: brandPrimary }">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <p class="text-[11px] font-bold leading-tight uppercase tracking-wider" :style="{ color: brandPrimary }">
                        <template v-if="store.config.frameType === 'vstavnaya' && store.config.measurementMethod === 'proem'">
                          ИЗМЕРИЛИ ОТКРЫТЫЙ ПРОЕМ ОТ КРАЯ ДО КРАЯ РЕЗИНКИ. <br/>МЫ АВТОМАТИЧЕСКИ УВЕЛИЧИЛИ РАЗМЕР НА 17 ММ ПО ШИРИНЕ И 12 ММ ПО ВЫСОТЕ.
                        </template>
                        <template v-else>
                          <span v-html="measurementMethods.find(m => m.id === store.config.measurementMethod)?.desc"></span>
                        </template>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Шаг 3: Оформление -->
              <div v-if="currentStep === 3" class="space-y-8 pt-2">
                <div class="bg-gray-50/50 rounded-3xl p-8 border border-gray-100 space-y-6 relative group">
                  <!-- Кнопка сброса (Крестик) -->
                  <button @click="currentStep = 1"
                          class="absolute top-6 right-6 w-8 h-8 flex items-center justify-center rounded-full bg-white border border-gray-100 text-gray-400 hover-brand-reset transition-all active:scale-90 z-10"
                          title="Начать сначала">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>

                  <h4 class="text-lg font-black text-brand-dark uppercase tracking-tight">Проверьте параметры</h4>

                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs">
                    <div class="space-y-1">
                      <p class="text-gray-400 font-bold uppercase tracking-wider">Тип сетки</p>
                      <p class="font-black text-brand-dark">{{ types.find(t => t.id === store.config.type)?.name }}</p>
                    </div>
                    <div class="space-y-1">
                      <p class="text-gray-400 font-bold uppercase tracking-wider">Тип рамки</p>
                      <p class="font-black text-brand-dark">{{ frameTypes.find(f => f.id === store.config.frameType)?.name }}</p>
                    </div>
                    <div class="space-y-1">
                      <p class="text-gray-400 font-bold uppercase tracking-wider">Цвет</p>
                      <p class="font-black text-brand-dark">{{ colors.find(c => c.id === store.config.color)?.name }}</p>
                    </div>
                    <div class="space-y-1">
                      <p class="text-gray-400 font-bold uppercase tracking-wider">Размеры изделия</p>
                      <p class="font-black text-brand-dark">{{ store.config.width }} x {{ store.config.height }} мм</p>
                    </div>
                    <div class="space-y-1">
                      <p class="text-gray-400 font-bold uppercase tracking-wider">Количество</p>
                      <p class="font-black text-brand-dark">{{ store.config.count }} шт.</p>
                    </div>
                    <div class="space-y-1">
                      <p class="text-gray-400 font-bold uppercase tracking-wider">Дополнительно</p>
                      <p class="font-black text-brand-dark">
                        {{ store.config.handleType === 'metal' ? 'Металл. ручки' : 'ПВХ ручки' }}{{ store.config.installation ? ', Монтаж' : ', Без монтажа' }}
                      </p>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </Transition>
        </div>

          <!-- Навигация и Цена: зафиксирована внизу правой части -->
          <div v-if="currentStep < 3" class="pt-6 pb-2 border-t border-gray-100 flex flex-col sm:flex-row justify-between items-center gap-8 bg-white mt-auto shrink-0">            <!-- Цена в левом углу -->
            <div class="text-center sm:text-left w-full sm:w-auto order-2 sm:order-1">
              <p class="text-[10px] text-gray-400 uppercase font-black tracking-[0.3em] mb-1">Предварительная цена</p>
              <div class="flex items-baseline justify-center sm:justify-start">
                <div class="inline-flex items-baseline gap-3 bg-white px-8 py-2 -ml-8 overflow-visible">
                  <span class="text-3xl font-black leading-none tracking-normal whitespace-nowrap" :style="{ color: brandPrimary }">{{ (store.currentPrice + (store.config.installation ? store.extrasInstallation : 0) + (store.config.handleType === 'metal' ? store.extrasHandleMetal : 0)) * store.config.count }}</span>
                  <span class="text-xl font-black text-gray-200 uppercase leading-none self-baseline">₽</span>
                </div>
              </div>
            </div>

            <!-- Кнопки навигации: «Далее» по ширине как «Назад», обе одинаковой ширины (сетка); pb-6 чтобы тень не обрезалась -->
          <div class="grid grid-cols-2 gap-4 w-full sm:w-auto order-1 sm:order-2 pb-6">
            <button v-if="currentStep > 1"
                    @click="prevStep"
                    class="w-full text-[10px] font-black text-gray-400 uppercase tracking-widest flex items-center justify-center gap-2 transition-colors py-3 px-6 border-2 border-gray-100 rounded-2xl nav-back-button"
                    :style="{ '--brand-primary': brandPrimary, '--hover-text-color': brandPrimary, '--hover-border-color': brandPrimary + '33' }">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M15 19l-7-7 7-7" />
              </svg>
              Назад
            </button>

            <button @click="nextStep"
                    :disabled="currentStep === 2 && !store.config.measurementMethod"
                    :class="[
                      'w-full font-black py-3 px-6 rounded-2xl transition-all uppercase text-[10px] tracking-widest flex items-center justify-center gap-2 shadow-xl active:scale-95 border-2 border-transparent',
                      currentStep === 1 ? 'col-span-2' : '',
                      currentStep === 2 && !store.config.measurementMethod
                        ? 'bg-gray-100 text-gray-300 cursor-not-allowed shadow-none'
                        : 'bg-brand-blue text-white hover:bg-[#1e5a9a] shadow-brand-blue/20 next-step-button'
                    ]"
                    :style="{ '--brand-primary': brandPrimary }">
              {{ currentStep === 2 && !store.config.measurementMethod ? 'Выберите метод замера' : 'Далее' }}
              <svg v-if="!(currentStep === 2 && !store.config.measurementMethod)" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

          <!-- Итоговая цена + Добавить в заказ: зафиксирована внизу для шага 3 -->
          <div v-if="currentStep === 3" class="pt-6 pb-2 border-t border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-6 bg-white mt-auto shrink-0">
            <div class="text-center sm:text-left w-full sm:w-auto">
              <p class="text-[10px] text-gray-400 uppercase font-black tracking-[0.3em] mb-1">Итоговая цена</p>
              <div class="flex items-baseline justify-center sm:justify-start">
                <div class="inline-flex items-baseline gap-3 bg-white px-8 py-2 -ml-8 overflow-visible">
                  <span class="text-5xl font-black leading-none tracking-normal whitespace-nowrap" :style="{ color: brandPrimary }">{{ (store.currentPrice + (store.config.installation ? store.extrasInstallation : 0) + (store.config.handleType === 'metal' ? store.extrasHandleMetal : 0)) * store.config.count }}</span>
                  <span class="text-2xl font-black text-gray-200 uppercase leading-none self-baseline" style="font-size: 1.5rem; line-height: 1;">₽</span>
                </div>
              </div>
            </div>
            <button @click="handleAddToOrder()"
                    :class="[
                      'w-full sm:w-auto font-black py-3 px-14 rounded-2xl transition-all shadow-xl active:scale-95 uppercase text-[10px] tracking-widest whitespace-nowrap add-to-order-button border-2',
                      isAdded ? 'text-white' : 'bg-brand-dark text-white border-transparent'
                    ]"
                    :style="[
                      isAdded ? { backgroundColor: brandPrimary, borderColor: brandPrimary } : {},
                      { '--brand-primary': brandPrimary }
                    ]">
              {{ isAdded ? 'Добавлено' : 'Добавить в заказ' }}
            </button>
          </div>
      </div>
    </div>

    <!-- Список заказа -->
    <div ref="orderBlockRef" v-if="store.items.length > 0" class="bg-white rounded-[3rem] shadow-2xl border border-gray-100 overflow-hidden transform animate-in fade-in slide-in-from-bottom-10 duration-700 scroll-mt-40">
      <div class="p-10 md:p-16">
        <div class="flex items-center justify-between mb-12">
          <div class="flex items-center gap-4">
            <div class="w-10 h-10 bg-brand-dark rounded-xl flex items-center justify-center text-white font-black text-sm shadow-lg shadow-black/10">
              1
            </div>
            <div class="flex flex-col">
              <h3 class="text-3xl font-black text-brand-dark uppercase tracking-tighter leading-none">Ваш заказ</h3>
              <button @click="scrollToCalculator" class="text-[10px] font-black uppercase tracking-widest mt-2 flex items-center gap-2 hover:opacity-70 transition-all group" :style="{ color: brandPrimary }">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 transform rotate-180 group-hover:-translate-y-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" :style="{ color: brandPrimary }">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M19 9l-7 7-7-7" />
                </svg>
                Добавить еще сетки
              </button>
            </div>
          </div>
          <button type="button" @click="store.clearOrder(); showOrderForm = false" class="text-gray-400 transition-colors p-2" :class="'hover:text-[' + brandPrimary + ']'" :style="{ '--hover-color': brandPrimary }" aria-label="Закрыть заказ">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 md:h-8 md:w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] border-b border-gray-100">
                <th class="pb-8 pr-4">Тип рамки</th>
                <th class="pb-8 px-4">Цвет рамки</th>
                <th class="pb-8 px-4">Тип полотна</th>
                <th class="pb-8 px-4">Тип замера</th>
                <th class="pb-8 px-4">Габариты</th>
                <th class="pb-8 px-4">Тип ручек</th>
                <th class="pb-8 px-4">Монтаж</th>
                <th class="pb-8 px-4">Кол-во</th>
                <th class="pb-8 px-4">Стоимость</th>
                <th class="pb-8 pl-4"></th>
              </tr>
            </thead>
            <tbody class="text-sm font-bold text-brand-dark">
              <tr v-for="item in store.items" :key="item.id" class="border-b border-gray-50 group hover:bg-gray-50/50 transition-colors">
                <td class="py-8 pr-4 uppercase text-xs font-black text-gray-600">{{ item.frameTypeName ?? '—' }}</td>
                <td class="py-8 px-4 uppercase text-xs font-black text-gray-600">{{ item.color }}</td>
                <td class="py-8 px-4 uppercase text-xs font-black text-brand-dark">{{ item.typeName.split(' (')[0] }}</td>
                <td class="py-8 px-4 text-xs font-medium text-gray-500 whitespace-nowrap">
                  {{ item.measurementMethod.replace(' ММ', ' мм') }}
                </td>
                <td class="py-8 px-4 text-xs text-gray-500 font-medium whitespace-nowrap">{{ item.width }} x {{ item.height }} мм</td>
                <td class="py-8 px-4 text-xs text-gray-500 font-medium whitespace-nowrap">
                  {{ item.typeName.includes('(МЕТАЛЛ)') ? 'МЕТАЛЛ' : 'ПВХ' }}
                </td>
                <td class="py-8 px-4 text-xs text-gray-500 font-medium whitespace-nowrap">
                  {{ item.typeName.includes(' + МОНТАЖ') ? 'ДА' : 'НЕТ' }}
                </td>
                <td class="py-8 px-4 text-xs text-gray-600 font-black whitespace-nowrap">{{ item.count }} шт</td>
                <td class="py-8 px-4 text-lg font-black" :style="{ color: brandPrimary }">{{ item.price }} ₽</td>
                <td class="py-8 pl-4 text-right">
                  <button @click="store.removeItem(item.id)" class="text-gray-200 transition-all transform hover:scale-110" :style="{ '--hover-red': brandPrimary }">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v2m3 3h.01" />
                    </svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-6 flex justify-end">
          <button @click="scrollToCalculator" class="text-[10px] font-black uppercase tracking-widest flex items-center gap-2 hover:opacity-70 transition-all group calc-link-brand">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 transform rotate-180 group-hover:-translate-y-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M19 9l-7 7-7-7" />
            </svg>
            Добавить еще сетки
          </button>
        </div>

        <div class="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          <!-- Опции -->
          <div class="bg-gray-50 p-5 sm:p-10 rounded-[2.5rem] space-y-8 min-w-0">
            <div class="flex items-center gap-4">
              <div class="w-10 h-10 bg-brand-dark rounded-xl flex items-center justify-center text-white font-black text-sm">
                {{ extrasCount }}
              </div>
              <h4 class="text-3xl font-black text-brand-dark uppercase tracking-tighter">Опции</h4>
            </div>

            <!-- 1. Способ получения (один из трёх), обязательно при заказе без монтажа; при смешанном — только доставка -->
            <div class="space-y-3">
              <p class="text-[10px] font-black text-gray-400 uppercase tracking-wider">Способ получения</p>
              <div class="grid grid-cols-1 gap-4">
                <template v-if="!store.allItemsWithInstallation || store.isMixedOrder">
                  <button v-for="d in (store.isMixedOrder ? deliveries.filter(x => x.id === 'Доставка') : deliveries)" :key="d.id"
                          type="button"
                          @click="store.setDelivery(d.id, d.price)"
                          :class="[
                            'flex justify-between items-center gap-3 p-5 rounded-2xl border-2 transition-all text-xs font-black uppercase tracking-wider text-left min-w-0',
                            store.delivery === d.id
                              ? 'bg-white shadow-xl scale-[1.02] option-selected'
                              : 'bg-transparent border-gray-200/50 text-gray-400 hover:border-gray-200 option-delivery'
                          ]"
                          :style="store.delivery === d.id ? { borderColor: brandPrimary, color: brandPrimary } : {}">
                    <span class="flex items-center gap-3 min-w-0 flex-1 break-words">
                      <!-- Иконка здания (самовывоз) -->
                      <span v-if="d.icon === 'building'" class="flex-shrink-0 w-5 h-5 text-current opacity-70">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                      </span>
                      <!-- Иконка грузовика (доставка) -->
                      <span v-else-if="d.icon === 'truck'" class="flex-shrink-0 w-5 h-5 text-current opacity-70">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12" />
                        </svg>
                      </span>
                      <span class="min-w-0">{{ d.name }}</span>
                    </span>
                    <span class="shrink-0 pl-2" :style="{ color: store.delivery === d.id ? brandPrimary : '#9ca3af' }">{{ d.price > 0 ? `${d.price} ₽` : '0 ₽' }}</span>
                  </button>
                </template>
                <template v-if="store.allItemsWithInstallation && !store.isMixedOrder">
                  <button type="button"
                          @click="store.setDiscount(store.discountType === urgentOrderOption.id ? '' : urgentOrderOption.id)"
                          :class="[
                            'flex justify-between items-center gap-3 p-5 rounded-2xl border-2 transition-all text-xs font-black uppercase tracking-wider text-left min-w-0 w-full option-urgent',
                            store.discountType === urgentOrderOption.id
                              ? 'bg-white shadow-xl scale-[1.02] option-selected'
                              : 'bg-transparent border-gray-200/50 text-gray-400 hover:border-gray-200'
                          ]"
                          :style="store.discountType === urgentOrderOption.id ? { borderColor: brandPrimary, color: brandPrimary } : {}">
                    <span class="flex items-center gap-3 min-w-0">
                      <span class="flex-shrink-0 w-5 h-5 text-current opacity-70">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </span>
                      <span class="min-w-0">{{ urgentOrderOption.name }}</span>
                    </span>
                    <span class="shrink-0" :style="{ color: store.discountType === urgentOrderOption.id ? brandPrimary : '#9ca3af' }">{{ urgentOrderOption.price }} ₽</span>
                  </button>
                </template>
              </div>
            </div>

            <!-- 2. Дополнительно: замер (можно добавить к способу получения), без чекбокса -->
            <div class="space-y-3">
              <p class="text-[10px] font-black text-gray-400 uppercase tracking-wider">Дополнительно</p>
              <button type="button"
                      @click="store.setMeasurement(!store.measurementSelected, measurementOption.price)"
                      :class="[
                        'flex justify-between items-center gap-3 w-full p-5 rounded-2xl border-2 transition-all text-xs font-black uppercase tracking-wider text-left min-w-0 option-measurement',
                        store.measurementSelected
                          ? 'bg-white shadow-xl scale-[1.02] option-selected'
                          : 'bg-transparent border-gray-200/50 text-gray-400 hover:border-gray-200'
                      ]"
                      :style="store.measurementSelected ? { borderColor: brandPrimary, color: brandPrimary } : {}">
                <span class="flex items-center gap-3 min-w-0 flex-1 break-words">
                  <!-- Иконка человечка (замер — приедет замерщик) -->
                  <span class="flex-shrink-0 w-5 h-5 text-current opacity-70">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                    </svg>
                  </span>
                  <span class="min-w-0">{{ measurementOption.name }}</span>
                </span>
                <span class="shrink-0 pl-2" :style="{ color: store.measurementSelected ? brandPrimary : '#9ca3af' }">{{ measurementOption.price }} ₽</span>
              </button>
            </div>

            <p class="text-[10px] text-gray-400 leading-relaxed">
              {{ store.allItemsWithInstallation ? 'При необходимости отметьте замер — его можно заказать вместе с монтажом.' : store.isMixedOrder ? 'При необходимости отметьте замер — его можно заказать вместе с доставкой и монтажом.' : 'При необходимости отметьте замер — его можно заказать вместе с доставкой или самовывозом.' }}
            </p>
          </div>

          <!-- Итого -->
          <div class="p-12 pb-20 sm:pb-12 rounded-[3rem] text-white shadow-[0_30px_100px_-10px_rgba(42,106,178,0.5)] relative overflow-hidden group"
               :style="{ backgroundColor: brandPrimary }">
            <div class="relative z-10">
              <p class="text-[10px] font-black uppercase tracking-[0.4em] opacity-50 mb-4">Итого к оплате</p>
              <div class="flex items-baseline gap-4 mb-8">
                <span class="text-7xl font-black tracking-tighter">{{ store.totalPrice }}</span>
                <span class="text-3xl font-black opacity-30">₽</span>
              </div>

              <!-- Блок ответственности (НАД кнопкой) -->
              <div class="mb-8 flex gap-4 items-start bg-white/5 p-5 rounded-2xl border border-white/10 relative z-10">
                <div class="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div class="space-y-1.5">
                  <p class="text-[10px] font-medium text-white/90 leading-tight uppercase tracking-wider">
                    <span v-if="!store.measurementSelected">Замер своими силами: ответственность на вас</span>
                    <span v-else>Замер мастером: ответственность наша</span>
                  </p>
                  <button type="button" @click="store.setMeasurement(!store.measurementSelected, store.measurementPriceCalculated)"
                          class="text-[10px] font-black text-white underline underline-offset-4 opacity-70 hover:opacity-100 transition-all uppercase tracking-widest text-left">
                    {{ store.measurementSelected ? 'Мастер приедет на замер' : 'Рекомендуем вызвать мастера' }}
                  </button>
                </div>
              </div>

              <button @click="openOrderForm()"
                      :disabled="!canSubmitOrder"
                      :class="[
                        'w-full font-black py-6 rounded-2xl transition-all uppercase text-xs tracking-[0.3em]',
                        canSubmitOrder
                          ? 'bg-white shadow-2xl active:scale-95 cursor-pointer checkout-button'
                          : 'bg-white/50 text-gray-400 cursor-not-allowed shadow-none'
                      ]"
                      :style="canSubmitOrder ? { color: brandPrimary, '--brand-primary': brandPrimary, '--hover-text-color': brandPrimary, '--hover-border-color': brandPrimary, '--hover-bg': '#f8fafc' } : {}">
                {{ !store.config.measurementMethod ? 'Выберите метод замера' : (canSubmitOrder ? 'Оформить заказ' : 'Выберите способ получения') }}
              </button>
            </div>

            <!-- Декор -->
            <div class="absolute -bottom-20 -right-20 w-64 h-64 bg-white/10 rounded-full blur-3xl group-hover:scale-110 transition-transform duration-700"></div>
            <div class="absolute -top-20 -left-20 w-40 h-40 bg-black/10 rounded-full blur-2xl"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Блок оформления заказа (под «Ваш заказ»): те же стили, скролл сюда по кнопке «Оформить заказ» -->
    <div ref="orderFormBlockRef" v-if="showOrderForm" class="bg-white rounded-[3rem] shadow-2xl border border-gray-100 overflow-hidden transform animate-in fade-in slide-in-from-bottom-10 duration-500 scroll-mt-40 mt-8 md:mt-12">
      <div class="p-10 md:p-16">
        <div class="flex items-center justify-between mb-12">
          <div class="flex items-center gap-4">
            <div class="w-10 h-10 bg-brand-dark rounded-xl flex items-center justify-center text-white shadow-lg shadow-black/10">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 class="text-3xl font-black text-brand-dark uppercase tracking-tighter">Оформление</h3>
          </div>
          <button type="button" @click="showOrderForm = false" class="text-gray-400 hover:text-brand-dark transition-colors p-2" aria-label="Свернуть">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 md:h-8 md:w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p class="text-gray-400 font-medium text-xs md:text-sm mb-10 ml-2">Заполните данные, и мы перезвоним для уточнения деталей</p>
        <form @submit.prevent="submitOrder" class="space-y-6 md:space-y-8 form-brand" :style="{ '--form-brand-primary': brandPrimary }">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
            <div class="space-y-3">
              <label class="text-[10px] font-black text-gray-400 uppercase tracking-wider ml-4">Ваше имя</label>
              <input v-model="form.name" type="text" required placeholder="Иван Иванов"
                     :class="[
                       'w-full bg-gray-50 border-2 focus:bg-white rounded-2xl md:rounded-3xl px-8 py-5 outline-none transition-all font-bold text-base shadow-inner',
                       formErrors.name ? 'border-red-500 focus:border-red-500' : 'border-transparent'
                     ]" />
              <p v-if="formErrors.name" class="text-red-500 text-xs font-bold ml-4">{{ formErrors.name }}</p>
            </div>
            <div class="space-y-3">
              <label class="text-[10px] font-black text-gray-400 uppercase tracking-wider ml-4">Телефон</label>
              <input :value="form.phone" type="tel" inputmode="tel" autocomplete="tel" required placeholder="+7 (___) ___-__-__"
                     @keydown="onPhoneKeydown"
                     @input="onPhoneInput"
                     maxlength="18"
                     :class="[
                       'w-full bg-gray-50 border-2 focus:bg-white rounded-2xl md:rounded-3xl px-8 py-5 outline-none transition-all font-bold text-base shadow-inner',
                       formErrors.phone ? 'border-red-500 focus:border-red-500' : 'border-transparent'
                     ]" />
              <p v-if="formErrors.phone" class="text-red-500 text-xs font-bold ml-4">{{ formErrors.phone }}</p>
            </div>
          </div>
          <div v-if="store.delivery === 'Доставка' || store.hasItemsWithInstallation || store.measurementSelected" class="space-y-3">
            <label class="text-[10px] font-black text-gray-400 uppercase tracking-wider ml-4">Адрес (для замера или доставки)</label>
            <input v-model="form.address" type="text" placeholder="Город, улица, дом, кв"
                   :class="[
                     'w-full bg-gray-50 border-2 focus:bg-white rounded-2xl md:rounded-3xl px-8 py-5 outline-none transition-all font-bold text-base shadow-inner',
                     formErrors.address ? 'border-red-500 focus:border-red-500' : 'border-transparent'
                   ]" />
            <p v-if="formErrors.address" class="text-red-500 text-xs font-bold ml-4">{{ formErrors.address }}</p>
          </div>
          <div class="space-y-3">
            <label class="text-[10px] font-black text-gray-400 uppercase tracking-wider ml-4">Комментарий</label>
            <textarea v-model="form.comment" rows="3" placeholder="Любые пожелания"
                      :class="[
                        'w-full bg-gray-50 border-2 focus:bg-white rounded-2xl md:rounded-3xl px-8 py-5 outline-none transition-all font-bold text-base shadow-inner resize-none',
                        formErrors.comment ? 'border-red-500 focus:border-red-500' : 'border-transparent'
                      ]"></textarea>
            <p v-if="formErrors.comment" class="text-red-500 text-xs font-bold ml-4">{{ formErrors.comment }}</p>
          </div>
          <label class="flex items-center gap-4 cursor-pointer group p-2">
            <div class="relative flex items-center">
              <input type="checkbox" v-model="form.showExtras" class="peer appearance-none w-7 h-7 border-2 border-gray-100 rounded-xl transition-all shadow-sm" :style="{ backgroundColor: form.showExtras ? brandPrimary : 'transparent', borderColor: form.showExtras ? brandPrimary : '#f3f4f6' }" />
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 absolute left-1 text-white opacity-0 peer-checked:opacity-100 transition-all scale-50 peer-checked:scale-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="4" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <span class="text-[10px] md:text-xs text-gray-400 font-black leading-tight uppercase tracking-widest group-hover:text-gray-600 transition-colors">
              Меня также интересуют окна, балконы, потолки или жалюзи <span :style="{ color: brandPrimary }">(отметьте, чтобы получить скидку 10% на эти услуги)</span>
            </span>
          </label>

          <transition name="fade-slide">
            <ExtraServices v-if="form.showExtras"
                           :options="extraServicesOptions"
                           :selected-ids="form.extraServices"
                           :brand-primary="brandPrimary"
                           @toggle="toggleExtraService" />
          </transition>

          <label class="flex items-center gap-4 cursor-pointer group p-2">
            <div class="relative flex items-center">
              <input type="checkbox" v-model="form.agree" required class="peer appearance-none w-7 h-7 border-2 border-gray-100 rounded-xl transition-all shadow-sm" :style="{ backgroundColor: form.agree ? brandPrimary : 'transparent', borderColor: form.agree ? brandPrimary : '#f3f4f6' }" />
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 absolute left-1 text-white opacity-0 peer-checked:opacity-100 transition-all scale-50 peer-checked:scale-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="4" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <span class="text-[10px] md:text-xs text-gray-400 font-black leading-none uppercase tracking-widest group-hover:text-gray-600 transition-colors">
              Я подтверждаю корректность размеров и даю согласие на <NuxtLink :to="privacyPolicyUrl" class="underline decoration-2 underline-offset-4" :style="{ color: brandPrimary }">обработку данных</NuxtLink>
            </span>
          </label>
          <div class="flex flex-col sm:flex-row gap-4 pt-4">
            <button type="submit"
                    :disabled="!form.agree"
                    class="flex-[2] font-black py-6 rounded-2xl transition-all shadow-2xl active:scale-95 uppercase text-xs tracking-[0.3em]"
                    :class="[
                      form.agree
                        ? 'text-white shadow-brand-blue/40 hover:shadow-brand-blue/60 hover:-translate-y-0.5'
                        : 'bg-gray-100 text-gray-300 cursor-not-allowed shadow-none'
                    ]"
                    :style="form.agree ? { backgroundColor: brandPrimary } : {}">
              Заказать
            </button>
            <button type="button" @click="showOrderForm = false"
                    @mouseenter="cancelHover = true"
                    @mouseleave="cancelHover = false"
                    class="flex-1 font-black py-6 rounded-2xl border-2 uppercase text-xs tracking-[0.3em] transition-all"
                    :style="{
                      '--hover-text-color': '#ffffff',
                      '--hover-border-color': brandPrimary,
                      backgroundColor: cancelHover ? brandPrimary : 'transparent',
                      borderColor: cancelHover ? brandPrimary : '#f3f4f6',
                      color: cancelHover ? '#ffffff' : '#9ca3af'
                    }">
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Уведомление -->
    <Teleport to="body">
      <div v-if="notification.show"
           class="fixed bottom-10 left-1/2 -translate-x-1/2 z-[100] transform animate-in fade-in slide-in-from-bottom-10 duration-500">
        <div :class="[
          'px-8 py-4 rounded-2xl shadow-2xl font-black text-sm uppercase tracking-widest flex items-center gap-4 border-2',
          notification.type === 'success' ? 'bg-white text-brand-dark' : 'bg-red-50 border-red-500 text-red-500'
        ]"
        :style="notification.type === 'success' ? { borderColor: brandPrimary, color: brandPrimary } : {}">
          <svg v-if="notification.type === 'success'" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {{ notification.message }}
        </div>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
input[type="range"]::-webkit-slider-thumb {
  @apply appearance-none w-8 h-8 bg-white border-[6px] border-brand-blue rounded-full shadow-[0_10px_25px_-5px_rgba(42,106,178,0.5)] cursor-pointer transition-all active:scale-125 active:shadow-brand-blue/60;
}

/* Стили для скроллбара в корзине */
.overflow-x-auto::-webkit-scrollbar {
  height: 6px;
}
.overflow-x-auto::-webkit-scrollbar-track {
  @apply bg-gray-50 rounded-full;
}
.overflow-x-auto::-webkit-scrollbar-thumb {
  @apply bg-gray-200 rounded-full hover:bg-gray-300 transition-colors;
}

/* Горизонтальный ползунок (ширина) — базовые стили для обоих */
.horizontal-range {  -webkit-appearance: none;
  appearance: none;
  height: 3px;
  background: #e5e7eb;
  border-radius: 9999px;
  outline: none;
  cursor: pointer;
}

.horizontal-range::-webkit-slider-runnable-track {
  height: 3px;
  background: #e5e7eb;
  border-radius: 9999px;
}

.horizontal-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: #3B82F6;
  border: none;
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  cursor: pointer;
  margin-top: -6.5px;
  transition: transform 0.15s ease;
}

.horizontal-range::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.horizontal-range::-webkit-slider-thumb:active {
  transform: scale(1.25);
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.15);
}

.horizontal-range::-moz-range-track {
  height: 3px;
  background: #e5e7eb;
  border-radius: 9999px;
}

.horizontal-range::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: #3B82F6;
  border: none;
  border-radius: 50%;
  cursor: pointer;
}

/* Скрываем нативный бегунок — используем кастомный overlay */
.hide-thumb {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  margin: auto 0;
  touch-action: none;
}
.hide-thumb::-webkit-slider-thumb {
  opacity: 0;
  width: 60px;
  height: 60px;
}
.hide-thumb::-moz-range-thumb {
  opacity: 0;
  width: 60px;
  height: 60px;
}

/* Анимации для Мастера */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Fix for hover on buttons with dynamic colors */
button:not([disabled]):not(.text-white):hover {
  border-color: var(--hover-border-color, #2A6AB233) !important;
  color: var(--hover-text-color, #2A6AB2) !important;
}

/* Ensure active buttons keep white text on hover */
button.text-white:hover {
  color: white !important;
}

/* Checkout button (Оформить заказ) hover state */
button.checkout-button:hover {
  background-color: white !important;
  color: var(--brand-primary, #2A6AB2) !important;
  border-color: var(--brand-primary, #2A6AB2) !important;
  box-shadow: 0 20px 25px -5px color-mix(in srgb, var(--brand-primary, #2A6AB2) 30%, transparent) !important;
  transform: translateY(-1px);
}

/* Add to order button (Добавить в заказ) hover state */
button.add-to-order-button:hover {
  background-color: white !important;
  color: var(--brand-primary, #2A6AB2) !important;
  border-color: var(--brand-primary, #2A6AB2) !important;
  box-shadow: 0 20px 25px -5px color-mix(in srgb, var(--brand-primary, #2A6AB2) 30%, transparent) !important;
  transform: translateY(-1px);
}

/* Next step button (Далее) hover state */
button.next-step-button:hover {
  background-color: white !important;
  color: var(--brand-primary, #2A6AB2) !important;
  border-color: var(--brand-primary, #2A6AB2) !important;
  box-shadow: 0 20px 25px -5px color-mix(in srgb, var(--brand-primary, #2A6AB2) 30%, transparent) !important;
  transform: translateY(-1px);
}

/* Hover на границу в цвет дилера */
.hover-brand-border:hover {
  border-color: var(--brand-primary, #2A6AB2) !important;
}
.hover-brand-border-light:hover {
  border-color: color-mix(in srgb, var(--brand-primary, #2A6AB2) 20%, transparent) !important;
}
.hover-brand-bg-light:hover {
  background-color: color-mix(in srgb, var(--brand-primary, #2A6AB2) 10%, transparent) !important;
}

/* Ссылка "Добавить еще сетки" */
.calc-link-brand {
  color: var(--brand-primary, #2A6AB2) !important;
}
.calc-link-brand:hover {
  opacity: 0.7 !important;
}

/* Nav Back button: всегда в цвет дилера при hover (приоритет над общим button:hover) */
button.nav-back-button:hover {
  color: var(--brand-primary) !important;
  border-color: var(--brand-primary) !important;
}

/* Опции в корзине: hover в цвет дилера */
button.option-selected:hover {
  opacity: 0.9;
  border-color: var(--brand-primary, #2A6AB2) !important;
  color: var(--brand-primary, #2A6AB2) !important;
}
button.option-selected:hover span {
  color: var(--brand-primary, #2A6AB2) !important;
}
button:not(.option-selected).option-delivery:hover,
button:not(.option-selected).option-urgent:hover,
button:not(.option-selected).option-measurement:hover {
  border-color: var(--brand-primary, #2A6AB2) !important;
  color: var(--brand-primary, #2A6AB2) !important;
  background-color: white !important;
}
button:not(.option-selected).option-delivery:hover span,
button:not(.option-selected).option-urgent:hover span,
button:not(.option-selected).option-measurement:hover span {
  color: var(--brand-primary, #2A6AB2) !important;
}

/* Close and Delete icons hover state */
button[aria-label="Закрыть заказ"]:hover,
button[aria-label="Свернуть"]:hover {
  color: var(--brand-primary, #2A6AB2) !important;
}

td.text-right button:hover {
  color: var(--brand-primary, #2A6AB2) !important;
}

/* Метод замера: hover в цвет дилера */
.measurement-method-btn {
  transition: all 0.3s ease;
}
button.measurement-method-btn:not(.text-white) {
  color: #9ca3af !important; /* text-gray-400 */
  border-color: #f3f4f6 !important; /* border-gray-100 */
  background-color: white !important;
}
button.measurement-method-btn:hover:not(.text-white) {
  border-color: var(--brand-primary, #2A6AB2) !important;
  color: var(--brand-primary, #2A6AB2) !important;
  background-color: white !important;
}

/* Стрелки опций (ПВХ/МЕТАЛЛ, Монтаж, Количество): цвет дилера только при hover */
.option-arrow {
  color: #e5e7eb !important; /* text-gray-200 */
  transition: all 0.3s ease;
}
button.option-arrow:hover {
  color: var(--brand-primary, #2A6AB2) !important;
  opacity: 1;
}

/* Ссылка "Добавить еще сетки" */
.calc-link-brand {
  color: var(--brand-primary, #2A6AB2) !important;
}
.calc-link-brand:hover {
  opacity: 0.7 !important;
}

/* Глобальные стили для ползунков (используются в Visualizer.vue) */
:deep(.horizontal-range) {
  -webkit-appearance: none;
  appearance: none;
  height: 3px;
  background: #e5e7eb;
  border-radius: 9999px;
  outline: none;
  cursor: pointer;
}

:deep(.hide-thumb::-webkit-slider-thumb) {
  -webkit-appearance: none;
  opacity: 0;
  width: 60px;
  height: 60px;
}

:deep(.hide-thumb::-moz-range-thumb) {
  opacity: 0;
  width: 60px;
  height: 60px;
}
</style>
