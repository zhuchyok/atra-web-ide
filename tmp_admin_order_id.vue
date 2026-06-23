<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const route = useRoute()

definePageMeta({
  layout: 'default',
  middleware: ['auth']
})

const orderId = computed(() => route.params.id as string)
const order = ref<any>(null)
const isLoading = ref(true)
const errorMessage = ref('')

const mapStatus = (status: string) => {
  const statuses: Record<string, string> = {
    new: 'Новый',
    confirmed: 'Подтверждён',
    in_production: 'В производстве',
    ready: 'Готов к выдаче',
    in_installation: 'На монтаже',
    completed: 'Завершён',
    cancelled: 'Отменён'
  }
  return statuses[status.toLowerCase()] || status
}

const translateKey = (key: string) => {
  const keys: Record<string, string> = {
    width: 'Ширина',
    height: 'Высота',
    mesh_type: 'Тип полотна',
    frame_type: 'Тип рамы',
    color: 'Цвет',
    color_id: 'ID цвета',
    handle_type: 'Ручки',
    installation: 'Монтаж',
    measurement_method: 'Метод замера',
    mounting_type: 'Монтаж'
  }
  return keys[key.toLowerCase()] || key
}

const translateValue = (val: any) => {
  if (typeof val === 'boolean') return val ? 'Да' : 'Нет'
  if (typeof val !== 'string') return val
  const values: Record<string, string> = {
    standart: 'Стандарт',
    antimoskit: 'Антимошка',
    antimoshka: 'Антимошка',
    antikoshka: 'Антикошка',
    ultravyu: 'Ультравью',
    ultravue: 'Ультравью',
    antipyl: 'Антипыль',
    vsn: 'Вставная VSN',
    ramochnaya: 'Рамочная',
    proem: 'По проему',
    stvorka: 'На створку',
    old_mesh: 'По старой сетке',
    pvc: 'ПВХ',
    metal: 'Металл'
  }
  return values[val.toLowerCase()] || val
}

const preferredParamOrder = ['mesh_type', 'frame_type', 'color', 'handle_type', 'installation', 'measurement_method']

const getOrderedParams = (params: Record<string, any>) => {
  const keys = Object.keys(params || {}).filter(key => !['width', 'height', 'color_id'].includes(key))
  return keys.sort((a, b) => {
    const aIdx = preferredParamOrder.indexOf(a)
    const bIdx = preferredParamOrder.indexOf(b)
    if (aIdx === -1 && bIdx === -1) return a.localeCompare(b)
    if (aIdx === -1) return 1
    if (bIdx === -1) return -1
    return aIdx - bIdx
  })
}

const formatPrice = (value: number | string) => new Intl.NumberFormat('ru-RU').format(Number(value || 0))

const fetchOrder = async () => {
  if (!orderId.value) return
  isLoading.value = true
  errorMessage.value = ''
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''

    const response = await $fetch<any>(`/api/v1/admin/orders/${orderId.value}`, {
      baseURL: apiBase,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    })

    order.value = response
  } catch (e) {
    console.error('Failed to fetch order', e)
    errorMessage.value = 'Не удалось загрузить детали заказа'
  } finally {
    isLoading.value = false
  }
}

useHead({
  title: computed(() => order.value ? `Заказ ${order.value.order_number} — Сетки 21` : 'Заказ — Сетки 21')
})

onMounted(fetchOrder)
</script>

<template>
  <div class="bg-gray-50 min-h-screen pb-20">
    <AdminHeader />

    <div class="container mx-auto px-4">
      <div class="flex items-center gap-4 mb-8">
        <NuxtLink to="/admin/orders" class="text-brand-blue hover:underline font-black text-[10px] uppercase tracking-widest">← Все заказы</NuxtLink>
      </div>

      <div v-if="isLoading" class="p-20 text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto mb-4"></div>
        <p class="text-gray-400 font-black uppercase text-[10px] tracking-widest">Загрузка...</p>
      </div>

      <div v-else-if="errorMessage || !order" class="bg-white rounded-[3rem] shadow-xl border border-gray-100 p-12 text-center">
        <p class="text-red-500 font-bold">{{ errorMessage || 'Заказ не найден' }}</p>
      </div>

      <div v-else class="flex flex-col gap-8">
        <!-- Шапка заказа -->
        <div class="bg-white rounded-[3rem] shadow-xl border border-gray-100 overflow-hidden">
          <div class="p-10 border-b border-gray-50 flex justify-between items-center">
            <div>
              <div class="flex items-center gap-4 mb-2">
                <h2 class="text-3xl font-black text-brand-dark uppercase tracking-tighter">Заказ {{ order.order_number }}</h2>
                <span class="px-4 py-1 rounded-full bg-blue-50 text-brand-blue text-[10px] font-black uppercase tracking-widest">
                  {{ mapStatus(order.status) }}
                </span>
              </div>
              <p class="text-gray-400 font-bold">{{ new Date(order.created_at).toLocaleString('ru-RU') }}</p>
            </div>
            <div class="text-right">
              <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Итого к оплате</p>
              <p class="text-4xl font-black text-brand-blue">{{ new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(order.total_amount) }}</p>
            </div>
          </div>

          <div class="p-10 grid grid-cols-1 md:grid-cols-3 gap-10 bg-gray-50/30">
            <div class="flex gap-4">
              <div class="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-brand-blue">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
              </div>
              <div>
                <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Клиент</p>
                <p class="font-black text-brand-dark text-lg">{{ order.client_name }}</p>
                <a :href="'tel:' + order.client_phone" class="text-brand-blue font-bold hover:underline">{{ order.client_phone }}</a>
              </div>
            </div>
            <div v-if="order.dealer_name" class="flex gap-4">
              <div class="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-brand-blue">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
              </div>
              <div>
                <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Дилер</p>
                <p class="font-black text-brand-dark text-lg">{{ order.dealer_name }}</p>
              </div>
            </div>
            <div v-if="order.client_address" class="flex gap-4">
              <div class="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-brand-blue">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              </div>
              <div>
                <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Адрес</p>
                <p class="font-black text-brand-dark">{{ order.client_address }}</p>
              </div>
            </div>
          </div>

          <div v-if="order.comment || order.extra_services" class="p-10 border-t border-gray-50 flex flex-col gap-6">
            <div v-if="order.comment" class="p-6 rounded-3xl bg-yellow-50/50 border border-yellow-100">
              <p class="text-[10px] font-black text-yellow-600 uppercase tracking-widest mb-2 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" /></svg>
                Комментарий клиента
              </p>
              <p class="text-brand-dark font-bold whitespace-pre-wrap">{{ order.comment }}</p>
            </div>

            <div v-if="order.extra_services" class="p-6 rounded-3xl bg-blue-50/50 border border-blue-100">
              <p class="text-[10px] font-black text-brand-blue uppercase tracking-widest mb-2 flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                Дополнительно интересует
              </p>
              <p class="text-brand-dark font-bold">{{ order.extra_services }}</p>
            </div>
          </div>
        </div>

        <!-- Состав заказа -->
        <div class="flex flex-col gap-6">
          <h3 class="text-2xl font-black text-brand-dark uppercase tracking-tighter px-4">Ваш заказ и опции</h3>

          <div v-for="(item, idx) in order.items" :key="item.id" class="bg-white rounded-[3rem] shadow-xl border border-gray-100 overflow-hidden">
            <div class="p-8 border-b border-gray-50 bg-gray-50/20 flex justify-between items-center">
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-full bg-brand-blue text-white flex items-center justify-center font-black text-sm">{{ idx + 1 }}</div>
                <h4 class="text-lg font-black text-brand-dark uppercase tracking-tight">{{ item.name }}</h4>
              </div>
              <div class="text-right">
                <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Количество</p>
                <p class="font-black text-xl text-brand-dark">{{ item.quantity }} шт.</p>
              </div>
            </div>

            <div class="p-8 grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div class="xl:col-span-2 space-y-5">
                <div v-if="item.params?.width || item.params?.height" class="p-6 rounded-3xl bg-blue-50/40 border border-blue-100">
                  <p class="text-[10px] font-black text-brand-blue uppercase tracking-widest mb-3">Размеры изделия (мм)</p>
                  <div class="flex items-end gap-4">
                    <div v-if="item.params?.width">
                      <p class="text-[8px] font-black text-gray-400 uppercase">Ширина</p>
                      <p class="text-2xl font-black text-brand-dark">{{ item.params.width }}</p>
                    </div>
                    <div class="text-gray-300 text-xl">×</div>
                    <div v-if="item.params?.height">
                      <p class="text-[8px] font-black text-gray-400 uppercase">Высота</p>
                      <p class="text-2xl font-black text-brand-dark">{{ item.params.height }}</p>
                    </div>
                  </div>
                </div>

                <div class="p-6 rounded-3xl bg-gray-50 border border-gray-100">
                  <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">Конструкция и материалы</p>
                  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    <div
                      v-for="key in getOrderedParams(item.params || {})"
                      :key="`${item.id}-${key}`"
                      class="px-4 py-3 rounded-2xl bg-white border border-gray-100 shadow-sm"
                    >
                      <p class="text-[8px] font-black text-gray-400 uppercase mb-1">{{ translateKey(key) }}</p>
                      <p class="text-xs font-black text-brand-dark break-words uppercase">{{ translateValue(item.params[key]) }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="p-6 rounded-3xl border border-brand-blue/20 bg-brand-blue/[0.03] flex flex-col justify-between">
                <div>
                  <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2">Цена за единицу</p>
                  <p class="text-3xl font-black text-brand-dark">{{ formatPrice(item.unit_price) }} ₽</p>
                </div>
                <div class="pt-5 mt-5 border-t border-brand-blue/10">
                  <p class="text-[10px] font-black text-brand-blue uppercase tracking-widest mb-2">Всего за {{ item.quantity }} шт.</p>
                  <p class="text-4xl font-black text-brand-blue">{{ formatPrice(item.total_price) }} ₽</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Дополнительные услуги -->
        <div v-if="order.installation_price || order.delivery_price || order.measurement_price" class="bg-white rounded-[3rem] shadow-xl border border-gray-100 overflow-hidden">
          <div class="p-8 border-b border-gray-50 bg-gray-50/20">
            <h3 class="text-lg font-black text-brand-dark uppercase tracking-tighter">Дополнительные опции</h3>
          </div>
          <div class="p-8 flex flex-wrap gap-6">
            <div v-if="order.measurement_price" class="flex-1 min-w-[200px] p-6 rounded-3xl bg-gray-50 border border-gray-100">
              <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Выезд мастера</p>
              <p class="text-xl font-black text-brand-dark">Замер</p>
              <p class="text-brand-blue font-black mt-2">{{ new Intl.NumberFormat('ru-RU').format(order.measurement_price) }} ₽</p>
            </div>
            <div v-if="order.delivery_price" class="flex-1 min-w-[200px] p-6 rounded-3xl bg-gray-50 border border-gray-100">
              <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Логистика</p>
              <p class="text-xl font-black text-brand-dark">Доставка</p>
              <p class="text-brand-blue font-black mt-2">{{ new Intl.NumberFormat('ru-RU').format(order.delivery_price) }} ₽</p>
            </div>
            <div v-if="order.installation_price" class="flex-1 min-w-[200px] p-6 rounded-3xl bg-gray-50 border border-gray-100">
              <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Работа на объекте</p>
              <p class="text-xl font-black text-brand-dark">Монтаж</p>
              <p class="text-brand-blue font-black mt-2">{{ new Intl.NumberFormat('ru-RU').format(order.installation_price) }} ₽</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
