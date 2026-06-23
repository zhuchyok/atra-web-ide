<script setup lang="ts">
import { reactive } from 'vue'
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()

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

definePageMeta({
  layout: 'default',
  middleware: ['auth']
})

const title = 'Управление дилерами — Сетки 21'
useHead({
  title
})

const dealers = ref([])
const isLoading = ref(true)
const isModalOpen = ref(false)
const isSaving = ref(false)
const isActivating = ref(false)
const activeTab = ref('basic')
const transactions = ref([])
const isTransactionsLoading = ref(false)
const dealerUsers = ref([])
const isUsersLoading = ref(false)
const isTopUpModalOpen = ref(false)
const topUpForm = reactive({
  amount: 0,
  description: ''
})
const isToppingUp = ref(false)
const generatedPassword = ref('')
const showPasswordModal = ref(false)
const isDealerLoading = ref(false)
const dealerBranches = ref<any[]>([])
const isBranchesLoading = ref(false)

const CATEGORY_KEYS = [
  'standart',
  'antimoshka',
  'antikoshka',
  'ultravyu',
  'antipyl',
  'vstavnaya'
] as const

const CATEGORY_LABELS: Record<(typeof CATEGORY_KEYS)[number], string> = {
  standart: 'СТАНДАРТНАЯ',
  antimoshka: 'АНТИМОШКА',
  antikoshka: 'АНТИКОШКА',
  ultravyu: 'УЛЬТРАВЬЮ',
  antipyl: 'АНТИПЫЛЬ',
  vstavnaya: 'ВСТАВНАЯ VSN'
}

const defaultCategoryCoefficients = () => ({
  standart: { dealer: 1.28, client: 2.13 },
  antimoshka: { dealer: 1.28, client: 2.13 },
  antikoshka: { dealer: 1.28, client: 2.13 },
  ultravyu: { dealer: 1.28, client: 2.13 },
  antipyl: { dealer: 1.28, client: 2.13 },
  vstavnaya: { dealer: 1.28, client: 2.13 }
})

const fetchTransactions = async (dealerId: string) => {
  transactions.value = []
  isTransactionsLoading.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''
    const response = await $fetch(`/api/v1/admin/dealers/${dealerId}/transactions`, {
      baseURL: apiBase,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    }) as any
    transactions.value = response
  } catch (e) {
    console.error('Failed to fetch transactions', e)
  } finally {
    isTransactionsLoading.value = false
  }
}

const fetchDealerUsers = async (dealerId: string) => {
  dealerUsers.value = []
  isUsersLoading.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''
    const response = await $fetch(`/api/v1/admin/dealers/${dealerId}/users`, {
      baseURL: apiBase,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    }) as any
    dealerUsers.value = response
  } catch (e) {
    console.error('Failed to fetch dealer users', e)
  } finally {
    isUsersLoading.value = false
  }
}

const fetchDealerBranches = async (dealerId: string) => {
  dealerBranches.value = []
  isBranchesLoading.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''
    const response = await $fetch(`/api/v1/cabinet/${dealerId}/branches`, {
      baseURL: apiBase,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    }) as any[]
    dealerBranches.value = response || []
  } catch (e) {
    console.error('Failed to fetch branches', e)
    dealerBranches.value = []
  } finally {
    isBranchesLoading.value = false
  }
}

watch(activeTab, (newTab) => {
  if (newTab === 'transactions' && form.id) {
    fetchTransactions(form.id)
  }
  if (newTab === 'users' && form.id) {
    fetchDealerUsers(form.id)
  }
  if (newTab === 'branches' && form.id) {
    fetchDealerBranches(form.id)
  }
})

const handleTopUp = async () => {
  if (!form.id || topUpForm.amount <= 0) return

  isToppingUp.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''

    const response = await $fetch(`/api/v1/admin/dealers/${form.id}/balance`, {
      method: 'POST',
      baseURL: apiBase,
      body: topUpForm,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    }) as any

    if (response.success) {
      showNotification(`Баланс пополнен на ${topUpForm.amount} ₽`)
      isTopUpModalOpen.value = false
      topUpForm.amount = 0
      topUpForm.description = ''
      // Обновляем баланс в форме и список транзакций
      form.balance = response.new_balance
      if (activeTab.value === 'transactions') {
        fetchTransactions(form.id)
      }
      await fetchDealers()
    }
  } catch (e) {
    console.error('Top up failed', e)
    showNotification('Ошибка при пополнении баланса', 'error')
  } finally {
    isToppingUp.value = false
  }
}

const handleActivateDomain = async () => {
  if (!form.id || !form.domain) return

  isActivating.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''

    const response = await $fetch(`/api/v1/admin/dealers/${form.id}/activate_domain`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${auth.token}` },
      baseURL: apiBase
    }) as any

    if (response.success) {
      showNotification(response.message || 'Домен успешно активирован')
    }
  } catch (e: any) {
    console.error('Activation failed', e)
    const msg = e.data?.message || 'Ошибка при активации домена'
    showNotification(msg, 'error')
  } finally {
    isActivating.value = false
  }
}

const form = reactive({
  id: null,
  name: '',
  city: '',
  phone: '',
  email: '',
  domain: '',
  margin_percent: 30.0,
  urgent_margin_percent: 0,
  delivery_margin_percent: 0,
  installation_margin_percent: 0,
  measurement_margin_percent: 0,
  category_coefficients: defaultCategoryCoefficients(),
  is_active: true,
  parent_id: null,
  role: 'dealer',
  credit_limit: 0,
  balance: 0,
  branding: {
    logo_url: '',
    primary_color: '#2196F3',
    short_description: '',
    full_description: '',
    working_hours: ''
  },
  contacts: {
    phones: [],
    emails: [],
    additional_cities: [],
    branches: [] as { id: string, name: string, address: string }[]
  },
  legal_info: {
    requisites: '',
    privacy_policy_url: '',
    privacy_policy_text: ''
  },
  seo_config: {
    title_template: '',
    description_template: '',
    keywords: '',
    verification_tag: '',
    analytics_code: ''
  }
})

const applyMarginConfigToForm = (source: any) => {
  const margin = source?.margin_config || {}
  form.margin_percent = Number(
    margin.base_margin_percent ?? source?.margin_percent ?? 30
  ) || 30
  form.urgent_margin_percent = Number(
    margin.urgent_margin_percent ?? source?.urgent_margin_percent ?? 0
  ) || 0
  form.delivery_margin_percent = Number(
    margin.delivery_margin_percent ?? source?.delivery_margin_percent ?? 0
  ) || 0
  form.installation_margin_percent = Number(
    margin.installation_margin_percent ?? source?.installation_margin_percent ?? 0
  ) || 0
  form.measurement_margin_percent = Number(
    margin.measurement_margin_percent ?? source?.measurement_margin_percent ?? 0
  ) || 0
  const incoming = margin.category_coefficients || {}
  const defaults = defaultCategoryCoefficients()
  CATEGORY_KEYS.forEach((key) => {
    const row = incoming?.[key] || {}
    form.category_coefficients[key].dealer = Number(row.dealer ?? defaults[key].dealer) || defaults[key].dealer
    form.category_coefficients[key].client = Number(row.client ?? defaults[key].client) || defaults[key].client
  })
}

const addBranch = () => {
  if (!form.contacts.branches) form.contacts.branches = []
  form.contacts.branches.push({
    id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(),
    name: '',
    address: ''
  })
}

const fetchDealers = async () => {
  isLoading.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''
    const response = await $fetch('/api/v1/admin/dealers', {
      baseURL: apiBase,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    }) as any
    dealers.value = response
  } catch (e) {
    console.error('Failed to fetch dealers', e)
  } finally {
    isLoading.value = false
  }
}

const openCreateModal = () => {
  form.id = null
  activeTab.value = "basic"
  form.name = ''
  form.city = ''
  form.phone = ''
  form.email = ''
  form.domain = ''
  form.margin_percent = 30.0
  form.urgent_margin_percent = 0
  form.delivery_margin_percent = 0
  form.installation_margin_percent = 0
  form.measurement_margin_percent = 0
  form.category_coefficients = defaultCategoryCoefficients()
  form.is_active = true
  form.parent_id = null
  form.role = 'dealer'
  form.credit_limit = 0
  form.balance = 0
  form.branding = { logo_url: '', primary_color: '#2196F3', short_description: '', full_description: '', working_hours: '' }
  form.contacts = { phones: [], emails: [], additional_cities: [] }
  form.legal_info = { requisites: '', privacy_policy_url: '', privacy_policy_text: '' }
  form.seo_config = {
    title_template: 'Москитные сетки в {city} - {dealer_name}',
    description_template: 'Заказать москитные сетки в {city} от производителя {dealer_name}. Изготовление за 1 день, замер и установка.',
    keywords: 'москитные сетки {city}, купить сетку на окно, {dealer_name}',
    verification_tag: '',
    analytics_code: ''
  }
  isModalOpen.value = true
}

// При открытии редактирования всегда подгружаем полные данные дилера с сервера, чтобы не затирать логотип и branding из устаревшего списка
const openEditModal = async (dealer: any) => {
  form.id = dealer.id
  activeTab.value = "basic"
  isModalOpen.value = true
  isDealerLoading.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''
    const full = await $fetch(`/api/v1/admin/dealers/${dealer.id}`, {
      baseURL: apiBase,
      headers: { Authorization: `Bearer ${auth.token}` }
    }) as any
    form.name = full.name
    form.city = full.city
    form.phone = full.phone
    form.email = full.email || ''
    form.domain = full.domain || ''
    applyMarginConfigToForm(full)
    form.is_active = full.is_active
    form.parent_id = full.parent_id
    form.role = full.role
    form.credit_limit = full.credit_limit
    form.balance = full.balance || 0
    form.branding = { ...full.branding, logo_url: full.branding?.logo_url ?? '' }
    form.contacts = { ...full.contacts }
    form.legal_info = { ...full.legal_info }
    form.seo_config = { ...full.seo_config }
  } catch (e) {
    console.error('Failed to load dealer for edit', e)
    // Fallback на данные из списка
    form.name = dealer.name
    form.city = dealer.city
    form.phone = dealer.phone
    form.email = dealer.email || ''
    form.domain = dealer.domain || ''
    applyMarginConfigToForm(dealer)
    form.is_active = dealer.is_active
    form.parent_id = dealer.parent_id
    form.role = dealer.role
    form.credit_limit = dealer.credit_limit
    form.balance = dealer.balance || 0
    form.branding = { ...dealer.branding }
    form.contacts = {
      phones: dealer.contacts?.phones || [],
      emails: dealer.contacts?.emails || [],
      additional_cities: dealer.contacts?.additional_cities || [],
      branches: dealer.contacts?.branches || []
    }
    form.legal_info = { ...dealer.legal_info }
    form.seo_config = { ...dealer.seo_config }
  } finally {
    isDealerLoading.value = false
  }
}

// В админке логотип показываем по полному URL к API, чтобы /uploads/... отдавал moskit-api
const displayLogoUrl = computed(() => {
  const u = form.branding?.logo_url
  if (!u) return ''
  if (u.startsWith('http')) return u
  const cfg = useRuntimeConfig()
  const base = (cfg.public.apiUrl as string) || ''
  return base ? base.replace(/\/$/, '') + u : u
})

const handleSave = async () => {
  isSaving.value = true
  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''

    const body = {
      ...form,
      domain: (form.domain && form.domain.trim()) || null,
      margin_config: {
        base_margin_percent: Number(form.margin_percent) || 30,
        city_multiplier: 1,
        branch_multiplier: 1,
        volume_discounts: [],
        category_margins: {},
        urgent_margin_percent: Number(form.urgent_margin_percent) || 0,
        delivery_margin_percent: Number(form.delivery_margin_percent) || 0,
        installation_margin_percent: Number(form.installation_margin_percent) || 0,
        measurement_margin_percent: Number(form.measurement_margin_percent) || 0,
        category_coefficients: CATEGORY_KEYS.reduce((acc, key) => {
          acc[key] = {
            dealer: Number(form.category_coefficients[key].dealer) || 1.28,
            client: Number(form.category_coefficients[key].client) || 2.13
          }
          return acc
        }, {} as Record<string, { dealer: number; client: number }>)
      }
    }
    let response: any
    if (form.id) {
      response = await $fetch(`/api/v1/admin/dealers/${form.id}`, {
        method: 'PUT',
        baseURL: apiBase,
        body,
        headers: { 'Authorization': `Bearer ${auth.token}` }
      })
    } else {
      response = await $fetch('/api/v1/admin/dealers', {
        method: 'POST',
        baseURL: apiBase,
        body,
        headers: { 'Authorization': `Bearer ${auth.token}` }
      })

      // Если это новый дилер и пришел пароль — показываем его
      if (response.initial_password) {
        generatedPassword.value = response.initial_password
        showPasswordModal.value = true
      }
    }

    await fetchDealers()
    showNotification('Данные дилера сохранены')
  } catch (e) {
    console.error('Failed to save dealer', e)
    showNotification('Ошибка при сохранении дилера', 'error')
  } finally {
    isSaving.value = false
  }
}

const handleLogoUpload = async (event: any) => {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const config = useRuntimeConfig()
    const apiBase = config.public.apiUrl || ''

    const response = await $fetch('/api/v1/admin/upload', {
      method: 'POST',
      baseURL: apiBase,
      body: formData,
      headers: { 'Authorization': `Bearer ${auth.token}` }
    }) as any

    if (response.url) {
      form.branding.logo_url = response.url
    }
  } catch (e) {
    console.error('Upload failed', e)
    showNotification('Ошибка при загрузке логотипа', 'error')
  }
}

onMounted(fetchDealers)
</script>

<template>
  <div class="bg-gray-50 min-h-screen pb-20">
    <AdminHeader />

    <div class="container mx-auto px-4">
      <div class="flex justify-between items-center mb-8">
        <div>
          <h2 class="text-2xl font-black text-brand-dark uppercase tracking-tighter">Список дилеров</h2>
        </div>
        <button @click="openCreateModal" class="admin-btn-primary font-black py-3 px-8 rounded-xl text-[10px] uppercase tracking-widest hover:scale-105 transition-transform">
          Добавить дилера
        </button>
      </div>
      <div v-if="isLoading" class="p-20 text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-blue mx-auto mb-4"></div>
        <p class="text-gray-400 font-black uppercase text-[10px] tracking-widest">Загрузка списка...</p>
      </div>
      <div v-else class="bg-white rounded-[3rem] shadow-2xl border border-gray-100 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="text-[10px] font-black text-gray-400 uppercase tracking-widest border-b border-gray-50">
                <th class="p-10">Название</th>
                <th class="p-10">Город</th>
                <th class="p-10">Статус</th>
                <th class="p-10"></th>
              </tr>
            </thead>
            <tbody class="text-sm font-bold text-brand-dark">
              <tr v-for="dealer in dealers" :key="dealer.id" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td class="p-10">
                  <div>{{ dealer.name }}</div>
                  <div class="text-[10px] text-gray-400 font-medium">{{ dealer.phone }}</div>
                </td>
                <td class="p-10 text-gray-400">{{ dealer.city }}</td>
                <td class="p-10">
                  <span :class="[
                    'px-4 py-2 rounded-full text-[10px] font-black uppercase tracking-widest',
                    dealer.is_active ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'
                  ]">
                    {{ dealer.is_active ? 'Активен' : 'Приостановлен' }}
                  </span>
                </td>
                <td class="p-10 text-right">
                  <button @click="openEditModal(dealer)" class="text-gray-300 hover:text-brand-blue transition-colors">Настроить</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Drawer (Выдвижная панель) -->
    <Teleport to="body">
      <Transition name="drawer">
        <div v-if="isModalOpen" class="fixed inset-0 z-[9999] flex justify-end">
          <!-- Overlay -->
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="isModalOpen = false"></div>

          <!-- Panel -->
          <div class="relative bg-white w-full max-w-2xl h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-500">
            <!-- Header -->
            <div class="p-8 border-b border-gray-50 flex justify-between items-center bg-gray-50/30">
              <div>
                <h3 class="text-2xl font-black text-brand-dark uppercase tracking-tighter">
                  {{ form.id ? 'Настройка дилера' : 'Новый дилер' }}
                  <span v-if="isDealerLoading" class="text-brand-blue font-normal normal-case text-sm ml-2">Загрузка…</span>
                </h3>
                <p v-if="form.id" class="text-[10px] font-black text-gray-400 uppercase tracking-widest mt-1">ID: {{ form.id }}</p>
              </div>
              <button type="button" @click="isModalOpen = false" class="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border-2 border-gray-100 text-[10px] font-black text-gray-400 uppercase tracking-widest hover:border-brand-blue/30 hover:text-brand-blue transition-all active:scale-[0.98]">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Закрыть
              </button>
            </div>

            <!-- Tabs -->
            <div class="px-8 pt-6 flex gap-2 overflow-x-auto no-scrollbar">
              <button @click="activeTab = 'basic'" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'basic' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Основное и Брендинг</button>
              <button @click="activeTab = 'hierarchy'" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'hierarchy' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Иерархия и Финансы</button>
              <button @click="activeTab = 'users'" v-if="form.id" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'users' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Пользователи</button>
              <button @click="activeTab = 'transactions'" v-if="form.id" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'transactions' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Транзакции</button>
              <button @click="activeTab = 'branches'" v-if="form.id" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'branches' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Филиалы и домены</button>
              <button @click="activeTab = 'contacts'" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'contacts' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Контакты</button>
              <button @click="activeTab = 'legal'" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'legal' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">Юр. данные</button>
              <button @click="activeTab = 'seo'" :class="['text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-xl transition-all whitespace-nowrap', activeTab === 'seo' ? 'bg-brand-blue text-white shadow-lg shadow-brand-blue/20' : 'text-gray-400 hover:bg-gray-50']">SEO и Аналитика</button>
            </div>

            <!-- Content -->
            <div class="flex-1 overflow-y-auto p-8 custom-scrollbar">
              <form @submit.prevent="handleSave" id="dealerForm" class="space-y-8">
                <div v-if="activeTab === 'basic'" class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Название компании</label>
                    <input v-model="form.name" type="text" required class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-2">
                      <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Город</label>
                      <input v-model="form.city" type="text" required class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                    </div>
                    <div class="space-y-2">
                      <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Телефон</label>
                      <input v-model="form.phone" type="text" required class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                    </div>
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Email для уведомлений</label>
                    <input v-model="form.email" type="email" required class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" placeholder="info@example.ru" />
                    <p class="text-[8px] text-gray-400 ml-4 uppercase">На этот адрес дилер будет получать заявки с сайта</p>
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Краткое описание (подпись)</label>
                    <input v-model="form.branding.short_description" type="text" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                  </div>

                  <!-- Привязка домена (NPM + SSL) -->
                  <div v-if="form.domain && form.id" class="pt-10 border-t border-gray-100 animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <div class="bg-gradient-to-br from-white to-blue-50/30 p-8 md:p-10 rounded-[3rem] border-2 border-blue-100/50 shadow-xl relative overflow-hidden group">
                      <!-- Декоративный элемент -->
                      <div class="absolute top-0 right-0 w-32 h-32 bg-brand-blue/5 rounded-full blur-3xl -mr-16 -mt-16 group-hover:bg-brand-blue/10 transition-colors duration-500"></div>

                      <div class="flex items-start gap-6 relative z-10">
                        <div class="w-14 h-14 bg-brand-blue rounded-2xl flex items-center justify-center text-white shadow-lg shadow-brand-blue/30 shrink-0">
                          <svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        </div>
                        <div class="flex-1">
                          <h3 class="text-xl font-black text-brand-dark uppercase tracking-tighter mb-2">Привязка домена</h3>
                          <p class="text-xs text-gray-500 font-bold uppercase tracking-wider mb-8 opacity-70">Настройка собственного адреса для дилера</p>

                          <div class="space-y-8">
                            <!-- Шаг 1 -->
                            <div class="space-y-4">
                              <div class="flex items-center gap-3">
                                <span class="text-[10px] font-black text-brand-blue uppercase tracking-widest bg-blue-50 px-3 py-1 rounded-lg">Шаг 1</span>
                                <h4 class="text-[10px] font-black text-brand-dark uppercase tracking-widest">Настройка DNS</h4>
                              </div>
                              <div class="bg-white/80 backdrop-blur-sm p-6 rounded-2xl border border-blue-100 shadow-inner">
                                <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest mb-3">Направьте домен на IP сервера:</p>
                                <div class="flex items-center gap-4">
                                  <code class="text-2xl font-black text-brand-blue tracking-tighter">45.10.43.248</code>
                                  <span class="text-[8px] font-black text-gray-300 uppercase tracking-widest">Создайте A-запись в панели регистратора</span>
                                </div>
                              </div>
                            </div>

                            <!-- Шаг 2 -->
                            <div class="space-y-4">
                              <div class="flex items-center gap-3">
                                <span class="text-[10px] font-black text-brand-blue uppercase tracking-widest bg-blue-50 px-3 py-1 rounded-lg">Шаг 2</span>
                                <h4 class="text-[10px] font-black text-brand-dark uppercase tracking-widest">Активация в системе</h4>
                              </div>
                              <button type="button"
                                      @click="handleActivateDomain"
                                      :disabled="isActivating"
                                      class="w-full bg-brand-dark text-white font-black py-5 rounded-2xl transition-all shadow-xl shadow-brand-dark/20 active:scale-[0.98] uppercase text-[10px] tracking-[0.2em] hover:bg-black group flex items-center justify-center gap-3 disabled:opacity-50">
                                <span v-if="isActivating" class="animate-pulse">Активация...</span>
                                <template v-else>
                                  <span class="group-hover:translate-x-1 transition-transform">Активировать сайт (NPM + SSL)</span>
                                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                                  </svg>
                                </template>
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Домен сайта</label>
                    <input v-model="form.domain" type="text" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" placeholder="setki21.ru или www.setki21.ru" />
                    <p class="text-[9px] text-gray-400 ml-4">Если указан — при заходе на этот домен подставляются настройки этого дилера (брендинг, контакты, SEO).</p>
                  </div>

                  <!-- Брендинг -->
                  <div class="pt-4 border-t border-gray-50 space-y-8">
                    <div class="space-y-2">
                      <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Логотип</label>
                      <div class="flex items-center gap-4 p-6 bg-gray-50 rounded-3xl border-2 border-dashed border-gray-200 hover:border-brand-blue transition-colors relative group">
                        <img v-if="form.branding.logo_url" :src="displayLogoUrl" alt="Логотип дилера" class="h-16 w-16 object-contain rounded-xl shadow-sm bg-white p-2" />
                        <div v-else class="h-16 w-16 bg-gray-200 rounded-xl flex items-center justify-center text-2xl">🖼️</div>
                        <div class="flex-1">
                          <input type="file" @change="handleLogoUpload" accept="image/*" class="absolute inset-0 opacity-0 cursor-pointer" />
                          <p class="text-[10px] font-black text-brand-blue uppercase tracking-widest">Загрузить файл</p>
                          <p class="text-[8px] text-gray-400 uppercase">PNG, JPG до 2MB</p>
                        </div>
                      </div>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div class="space-y-2">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Основной цвет</label>
                        <div class="flex gap-4">
                          <input v-model="form.branding.primary_color" type="color" class="h-14 w-20 bg-gray-50 border-2 border-transparent rounded-2xl outline-none cursor-pointer" />
                          <input v-model="form.branding.primary_color" type="text" class="flex-1 bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                        </div>
                      </div>
                      <div class="space-y-2">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Режим работы</label>
                        <input v-model="form.branding.working_hours" type="text" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" placeholder="Пн-Пт 9:00-18:00" />
                      </div>
                    </div>
                  </div>
                  <div class="space-y-6 pt-4 border-t border-gray-50">
                    <h4 class="text-[10px] font-black text-brand-blue uppercase tracking-[0.2em] ml-4">Дополнительные наценки (%)</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div class="space-y-2">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Срочность</label>
                        <input v-model.number="form.urgent_margin_percent" type="number" step="0.1" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                      </div>
                      <div class="space-y-2">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Доставка</label>
                        <input v-model.number="form.delivery_margin_percent" type="number" step="0.1" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                      </div>
                      <div class="space-y-2">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Монтаж</label>
                        <input v-model.number="form.installation_margin_percent" type="number" step="0.1" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                      </div>
                      <div class="space-y-2">
                        <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Замер</label>
                        <input v-model.number="form.measurement_margin_percent" type="number" step="0.1" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                      </div>
                    </div>
                    <p class="text-[8px] text-gray-400 ml-4 uppercase">Наценки применяются к рекомендованным розничным ценам на соответствующие услуги</p>
                  </div>

                  <div class="space-y-6 pt-4 border-t border-gray-50">
                    <h4 class="text-[10px] font-black text-brand-blue uppercase tracking-[0.2em] ml-4">Коэффициенты наценки по категориям</h4>
                    <p class="text-[8px] text-gray-400 ml-4 uppercase">Коэф. клиента — наценка от цены дилера производителя для клиента. Коэф. дилера — наценка от цены дилера производителя для дилеров текущего дилера.</p>
                    <div class="space-y-4">
                      <div
                        v-for="key in CATEGORY_KEYS"
                        :key="key"
                        class="grid grid-cols-1 md:grid-cols-3 gap-4 bg-gray-50 p-4 rounded-2xl"
                      >
                        <div class="text-[10px] font-black text-gray-500 uppercase tracking-widest flex items-center">
                          {{ CATEGORY_LABELS[key] }}
                        </div>
                        <div class="space-y-2">
                          <label class="text-[9px] font-black text-gray-400 uppercase tracking-widest ml-2">Коэф. наценки дилера</label>
                          <input
                            v-model.number="form.category_coefficients[key].dealer"
                            type="number"
                            step="0.01"
                            class="w-full bg-white border-2 border-transparent focus:border-brand-blue rounded-2xl px-4 py-3 outline-none font-bold shadow-inner"
                          />
                        </div>
                        <div class="space-y-2">
                          <label class="text-[9px] font-black text-gray-400 uppercase tracking-widest ml-2">Коэф. наценки клиента</label>
                          <input
                            v-model.number="form.category_coefficients[key].client"
                            type="number"
                            step="0.01"
                            class="w-full bg-white border-2 border-transparent focus:border-brand-blue rounded-2xl px-4 py-3 outline-none font-bold shadow-inner"
                          />
                        </div>
                      </div>
                    </div>
                    <p class="text-[8px] text-gray-400 ml-4 uppercase">По умолчанию: дилер 1.28, клиент 2.13. Используется в расчете стоимости сеток по типу полотна.</p>
                  </div>
                </div>

                <div v-if="activeTab === 'hierarchy'" class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Роль в системе</label>
                    <select v-model="form.role" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner">
                      <option value="owner">Владелец (Owner)</option>
                      <option value="director">Директор (Main Dealer)</option>
                      <option value="manager">Менеджер</option>
                      <option value="subdealer">Суб-дилер</option>
                    </select>
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Родительский дилер (Director)</label>
                    <select v-model="form.parent_id" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner">
                      <option :value="null">Нет (Главный)</option>
                      <option v-for="d in dealers.filter(x => x.id !== form.id)" :key="d.id" :value="d.id">{{ d.name }}</option>
                    </select>
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Кредитный лимит (₽)</label>
                    <input v-model.number="form.credit_limit" type="number" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                  </div>

                  <!-- Баланс -->
                  <div class="pt-6 border-t border-gray-100">
                    <div class="bg-brand-dark/5 p-8 rounded-[2rem] border border-brand-dark/10">
                      <div class="flex justify-between items-center mb-6">
                        <div>
                          <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Текущий баланс</p>
                          <p class="text-3xl font-black text-brand-dark tracking-tighter">{{ form.balance?.toLocaleString() }} ₽</p>
                        </div>
                        <button type="button" @click="isTopUpModalOpen = true" class="admin-btn-primary font-black py-3 px-6 rounded-xl text-[10px] uppercase tracking-widest hover:scale-105 transition-transform">
                          Пополнить
                        </button>
                      </div>
                      <p class="text-[9px] text-gray-400 uppercase font-bold">Баланс используется для оплаты заказов. Если баланс + лимит < 0, создание заказов блокируется.</p>
                    </div>
                  </div>
                </div>

                <div v-if="activeTab === 'users'" class="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div v-if="isUsersLoading" class="p-10 text-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue mx-auto"></div>
                  </div>
                  <div v-else-if="dealerUsers.length === 0" class="p-10 text-center text-gray-400 uppercase text-[10px] font-black tracking-widest">
                    Пользователей не найдено
                  </div>
                  <div v-else class="space-y-3">
                    <div v-for="user in dealerUsers" :key="user.id" class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex justify-between items-center">
                      <div>
                        <p class="text-sm font-black text-brand-dark uppercase tracking-tight">{{ user.name }}</p>
                        <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest mt-1">{{ user.email }}</p>
                      </div>
                      <div class="text-right">
                        <span class="px-3 py-1 bg-blue-50 text-brand-blue rounded-lg text-[10px] font-black uppercase tracking-widest">
                          {{ user.role }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p class="text-[8px] text-gray-400 uppercase text-center px-10">
                    При создании дилера автоматически создается один пользователь с ролью Dealer и указанным Email.
                  </p>
                </div>

                <div v-if="activeTab === 'branches'" class="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <p class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Филиалы и привязанные домены (настройка — в кабинете директора)</p>
                  <div v-if="isBranchesLoading" class="p-10 text-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue mx-auto"></div>
                  </div>
                  <div v-else-if="dealerBranches.length === 0" class="p-10 text-center text-gray-400 uppercase text-[10px] font-black tracking-widest">
                    Филиалов нет
                  </div>
                  <div v-else class="overflow-x-auto">
                    <table class="w-full text-left border border-gray-100 rounded-2xl overflow-hidden">
                      <thead class="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest">
                        <tr>
                          <th class="px-6 py-4">Филиал</th>
                          <th class="px-6 py-4">Домен</th>
                          <th class="px-6 py-4">Город</th>
                        </tr>
                      </thead>
                      <tbody class="text-sm font-bold text-brand-dark divide-y divide-gray-100">
                        <tr v-for="b in dealerBranches" :key="b.id" class="hover:bg-gray-50">
                          <td class="px-6 py-4">{{ b.name }}</td>
                          <td class="px-6 py-4 text-brand-blue">{{ b.domain || '—' }}</td>
                          <td class="px-6 py-4 text-gray-600">{{ b.city || '—' }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div v-if="activeTab === 'transactions'" class="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div v-if="isTransactionsLoading" class="p-10 text-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue mx-auto"></div>
                  </div>
                  <div v-else-if="transactions.length === 0" class="p-10 text-center text-gray-400 uppercase text-[10px] font-black tracking-widest">
                    Транзакций пока нет
                  </div>
                  <div v-else class="space-y-3">
                    <div v-for="tx in transactions" :key="tx.id" class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex justify-between items-center">
                      <div>
                        <div class="flex items-center gap-2 mb-1">
                          <span :class="['w-2 h-2 rounded-full', tx.amount > 0 ? 'bg-green-500' : 'bg-red-500']"></span>
                          <p class="text-[10px] font-black text-brand-dark uppercase tracking-widest">
                            {{ tx.type === 'deposit' ? 'Пополнение' : tx.type === 'order_payment' ? 'Оплата заказа' : tx.type }}
                          </p>
                        </div>
                        <p class="text-xs text-gray-400 font-bold">{{ new Date(tx.created_at).toLocaleString() }}</p>
                        <p v-if="tx.description" class="text-[10px] text-gray-500 mt-2 italic">{{ tx.description }}</p>
                      </div>
                      <div class="text-right">
                        <p :class="['text-lg font-black tracking-tighter', tx.amount > 0 ? 'text-green-600' : 'text-red-600']">
                          {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount.toLocaleString() }} ₽
                        </p>
                        <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Остаток: {{ tx.balance_after.toLocaleString() }} ₽</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="activeTab === 'contacts'" class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div class="space-y-4">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Дополнительные телефоны</label>
                    <div v-for="(p, i) in form.contacts.phones" :key="i" class="flex gap-2">
                      <input v-model="form.contacts.phones[i]" type="text" class="flex-1 bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                      <button @click="form.contacts.phones.splice(i, 1)" type="button" class="text-red-400 px-4 hover:scale-125 transition-transform">×</button>
                    </div>
                    <button @click="form.contacts.phones.push('')" type="button" class="text-[10px] font-black text-brand-blue uppercase tracking-widest ml-4 flex items-center gap-2 hover:opacity-70 transition-all">
                      <span class="w-6 h-6 rounded-lg bg-brand-blue/10 flex items-center justify-center">+</span>
                      Добавить телефон
                    </button>
                  </div>

                  <div class="pt-8 border-t border-gray-50 space-y-6">
                    <div class="flex justify-between items-center ml-4">
                      <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Пункты самовывоза (офисы)</label>
                      <button @click="addBranch" type="button" class="text-[10px] font-black text-brand-blue uppercase tracking-widest hover:underline">+ Добавить офис</button>
                    </div>

                    <div v-if="!form.contacts.branches || form.contacts.branches.length === 0" class="p-10 text-center bg-gray-50 rounded-3xl border-2 border-dashed border-gray-100">
                      <p class="text-[10px] font-black text-gray-300 uppercase tracking-widest">Офисы не добавлены. Будет использоваться город по умолчанию.</p>
                    </div>

                    <div v-for="(branch, i) in form.contacts.branches" :key="branch.id || i" class="bg-gray-50 p-6 rounded-3xl space-y-4 relative group">
                      <button @click="form.contacts.branches.splice(i, 1)" type="button" class="absolute top-4 right-4 text-red-400 opacity-0 group-hover:opacity-100 transition-all hover:scale-125">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v2m3 3h.01" />
                        </svg>
                      </button>

                      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="space-y-2">
                          <label class="text-[8px] font-black text-gray-400 uppercase tracking-widest ml-2">Название</label>
                          <input v-model="branch.name" type="text" class="w-full bg-white border-2 border-transparent focus:border-brand-blue rounded-xl px-4 py-3 outline-none font-bold text-sm shadow-sm" placeholder="Название офиса" />
                        </div>
                        <div class="space-y-2">
                          <label class="text-[8px] font-black text-gray-400 uppercase tracking-widest ml-2">Адрес</label>
                          <input v-model="branch.address" type="text" class="w-full bg-white border-2 border-transparent focus:border-brand-blue rounded-xl px-4 py-3 outline-none font-bold text-sm shadow-sm" placeholder="ул. Ленина, д. 1" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="activeTab === 'legal'" class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Реквизиты</label>
                    <textarea v-model="form.legal_info.requisites" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner resize-none" rows="6"></textarea>
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">URL политики конфиденциальности</label>
                    <input v-model="form.legal_info.privacy_policy_url" type="text" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                  </div>
                  <div class="flex items-center gap-4 p-6 bg-gray-50 rounded-3xl border-2 border-transparent hover:border-brand-blue/10 transition-all group cursor-pointer" @click="form.is_active = !form.is_active">
                    <div :class="['w-12 h-6 rounded-full relative transition-all duration-300', form.is_active ? 'bg-brand-blue' : 'bg-gray-200']">
                      <div :class="['absolute top-1 w-4 h-4 bg-white rounded-full transition-all duration-300', form.is_active ? 'left-7' : 'left-1']"></div>
                    </div>
                    <label class="text-xs font-black uppercase tracking-widest text-brand-dark cursor-pointer">Активный партнер</label>
                  </div>
                </div>

                <div v-if="activeTab === 'seo'" class="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Шаблон Title</label>
                    <input v-model="form.seo_config.title_template" type="text" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" placeholder="Москитные сетки в {city} - {dealer_name}" />
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Шаблон Description</label>
                    <textarea v-model="form.seo_config.description_template" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner resize-none" rows="3"></textarea>
                  </div>
                  <div class="space-y-2">
                    <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Keywords</label>
                    <input v-model="form.seo_config.keywords" type="text" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner" />
                  </div>
                  <div class="pt-6 border-t border-gray-100 space-y-8">
                    <div class="space-y-2">
                      <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Мета-тег подтверждения (Yandex/Google)</label>
                      <textarea v-model="form.seo_config.verification_tag" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-mono text-xs shadow-inner resize-none" rows="2" placeholder='<meta name="yandex-verification" content="..." />'></textarea>
                      <p class="text-[8px] text-gray-400 ml-4 uppercase">Будет вставлен в секцию &lt;head&gt;</p>
                    </div>
                    <div class="space-y-2">
                      <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Код счетчика (Метрика/Analytics)</label>
                      <textarea v-model="form.seo_config.analytics_code" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-mono text-xs shadow-inner resize-none" rows="6" placeholder="<!-- Yandex.Metrika counter --> ..."></textarea>
                      <p class="text-[8px] text-gray-400 ml-4 uppercase">Будет вставлен в конец &lt;body&gt;</p>
                    </div>
                  </div>
                </div>

              </form>
            </div>

            <!-- Footer -->
            <div class="p-8 border-t border-gray-50 bg-gray-50/30 flex gap-4">
              <button type="button" @click="isModalOpen = false" class="flex-1 py-5 rounded-2xl font-black text-[10px] uppercase tracking-widest text-gray-400 hover:bg-white hover:shadow-lg transition-all active:scale-95">Отмена</button>
              <button type="submit" form="dealerForm" :disabled="isSaving" class="flex-[2] admin-btn-primary py-5 rounded-2xl font-black text-[10px] uppercase tracking-widest hover:-translate-y-0.5 transition-all disabled:opacity-50 active:scale-95">
                {{ isSaving ? 'Сохранение...' : 'Сохранить изменения' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Модальное окно пополнения баланса -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showPasswordModal" class="fixed inset-0 z-[10000] flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showPasswordModal = false"></div>
          <div class="relative bg-white w-full max-w-md rounded-[3rem] shadow-2xl p-10 animate-in zoom-in-95 duration-300 text-center">
            <div class="w-20 h-20 bg-green-50 text-green-500 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-green-100">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 class="text-2xl font-black text-brand-dark uppercase tracking-tighter mb-2">Дилер создан!</h3>
            <p class="text-xs text-gray-400 font-bold uppercase tracking-widest mb-8">Передайте эти данные дилеру для входа</p>

            <div class="bg-gray-50 p-8 rounded-[2rem] border-2 border-dashed border-gray-200 mb-8 space-y-4">
              <div>
                <p class="text-[8px] font-black text-gray-400 uppercase tracking-widest mb-1">Логин (Email)</p>
                <p class="text-lg font-black text-brand-dark">{{ form.email }}</p>
              </div>
              <div class="pt-4 border-t border-gray-100">
                <p class="text-[8px] font-black text-gray-400 uppercase tracking-widest mb-1">Временный пароль</p>
                <p class="text-3xl font-black text-brand-blue tracking-widest">{{ generatedPassword }}</p>
              </div>
            </div>

            <button @click="showPasswordModal = false" class="w-full bg-brand-dark text-white py-5 rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-xl shadow-brand-dark/20 hover:bg-black transition-all active:scale-95">
              Я сохранил данные
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Модальное окно пополнения баланса -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="isTopUpModalOpen" class="fixed inset-0 z-[10000] flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="isTopUpModalOpen = false"></div>
          <div class="relative bg-white w-full max-w-md rounded-[3rem] shadow-2xl p-10 animate-in zoom-in-95 duration-300">
            <h3 class="text-2xl font-black text-brand-dark uppercase tracking-tighter mb-8 text-center">Пополнение баланса</h3>

            <form @submit.prevent="handleTopUp" class="space-y-6">
              <div class="space-y-2">
                <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Сумма (₽)</label>
                <input v-model.number="topUpForm.amount" type="number" required min="1" step="0.01" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner text-2xl text-brand-blue" />
              </div>

              <div class="space-y-2">
                <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-4">Комментарий</label>
                <textarea v-model="topUpForm.description" class="w-full bg-gray-50 border-2 border-transparent focus:border-brand-blue rounded-2xl px-6 py-4 outline-none font-bold shadow-inner resize-none" rows="3" placeholder="Например: Пополнение через кассу"></textarea>
              </div>

              <div class="flex gap-4 pt-4">
                <button type="button" @click="isTopUpModalOpen = false" class="flex-1 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest text-gray-400 hover:bg-gray-50 transition-all">Отмена</button>
                <button type="submit" :disabled="isToppingUp || topUpForm.amount <= 0" class="flex-[2] admin-btn-primary py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest transition-all disabled:opacity-50 active:scale-95">
                  {{ isToppingUp ? 'Пополнение...' : 'Пополнить баланс' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Уведомление -->
    <Teleport to="body">
      <div v-if="notification.show"
           class="fixed bottom-10 left-1/2 -translate-x-1/2 z-[100] transform animate-in fade-in slide-in-from-bottom-10 duration-500">
        <div :class="[
          'px-8 py-4 rounded-2xl shadow-2xl font-black text-sm uppercase tracking-widest flex items-center gap-4 border-2',
          notification.type === 'success' ? 'bg-white border-brand-blue text-brand-blue' : 'bg-red-50 border-red-500 text-red-500'
        ]">
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
.drawer-enter-active,
.drawer-leave-active {
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e5e7eb;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #d1d5db;
}
</style>
