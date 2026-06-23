<script setup lang="ts">
/**
 * Модальное окно «Заказать обратный звонок»: имя, телефон, чекбокс политики конфиденциальности.
 * На главном сайте отправка на основной email; у дилеров — на email дилера (передаётся toEmail).
 */

interface Props {
  /** Email получателя (для дилера); если не передан — бэкенд использует CONTACT_EMAIL */
  toEmail?: string
}

const props = defineProps<Props>()

const isModalOpen = defineModel<boolean>('open', { default: false })

const form = reactive({
  name: '',
  phone: '',
  agree: false,
  showExtras: false,
  extraServices: [] as string[]
})

const extraServicesOptions = [
  {
    id: 'windows',
    name: 'Окна и остекление',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-10 h-10">
      <path d="M3 3h18v18H3zM12 3v18M3 12h18M9 3v9M15 3v9M9 12v9M15 12v9" />
    </svg>`
  },
  {
    id: 'balcony',
    name: 'Отделка балконов',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-10 h-10">
      <path d="M3 11h18M3 15h18M3 19h18M5 11v8M9 11v8M13 11v8M17 11v8M19 11v8M3 7h18l-2-4H5z" />
    </svg>`
  },
  {
    id: 'ceilings',
    name: 'Натяжные потолки',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-10 h-10">
      <path d="M3 8l9-3 9 3v4l-9 3-9-3z" />
      <path d="M7 14l-1 3M12 16v3M17 14l1 3" />
      <path d="M12 2l1 1.5M4 6l1.5.5M20 6l-1.5.5" />
    </svg>`
  },
  {
    id: 'blinds',
    name: 'Жалюзи',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-10 h-10">
      <path d="M4 3h16M4 7h16M4 11h16M4 15h16M4 19h16M8 3v16" />
    </svg>`
  },
  {
    id: 'doors',
    name: 'Двери',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-10 h-10">
      <path d="M5 3h14v18H5zM15 12v.01" />
    </svg>`
  }
]

const toggleExtraService = (id: string) => {
  const index = form.extraServices.indexOf(id)
  if (index === -1) {
    form.extraServices.push(id)
  } else {
    form.extraServices.splice(index, 1)
  }
}

const formErrors = reactive<Record<string, string>>({ name: '', phone: '' })
const submitError = ref('')
const isLoading = ref(false)
const submitSuccess = ref(false)

const tenant = useTenantStore()
const workingHoursText = computed(() => tenant.config?.branding?.working_hours?.trim() || 'Пн–Пт 10:00–18:00')
// Ссылка на политику конфиденциальности из админки дилера (legal.privacy_policy_url) или дефолт /privacy
const privacyPolicyUrl = computed(() => tenant.config?.legal?.privacy_policy_url?.trim() || '/privacy')
const brandPrimary = computed(() => tenant.config?.branding?.primary_color || '#2A6AB2')

const PHONE_REGEX = /^\+7\s?\(\d{3,4}\)\s?\d{2,3}-\d{2}-\d{2}$|^\+7\d{10}$/
const PHONE_ALLOWED = /[\d+\s()\-]/g
const MAX_PHONE_DIGITS = 11
const PHONE_KEY_ALLOWED = /^[\d+\s\-()]$/

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

function sanitizePhoneInput(value: string): string {
  const allowed = (value.match(PHONE_ALLOWED) || []).join('')
  if (!allowed.replace(/\D/g, '').length) return ''
  return formatPhoneDisplay(allowed)
}

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

function validateForm(): boolean {
  formErrors.name = ''
  formErrors.phone = ''
  submitError.value = ''
  let valid = true
  if (!form.name.trim()) {
    formErrors.name = 'Введите имя'
    valid = false
  }
  const phone = form.phone.trim()
  if (!phone) {
    formErrors.phone = 'Введите телефон'
    valid = false
  } else if (!PHONE_REGEX.test(phone.replace(/\s/g, ''))) {
    formErrors.phone = 'Формат: +7 (XXX) XXX-XX-XX'
    valid = false
  }
  if (!form.agree) {
    submitError.value = 'Необходимо согласие с политикой конфиденциальности'
    valid = false
  }
  return valid
}

async function handleSubmit() {
  if (!validateForm()) return

  isLoading.value = true
  submitError.value = ''

  try {
    const body: Record<string, string | boolean> = {
      name: form.name.trim(),
      phone: form.phone.trim(),
      agreePrivacy: form.agree,
      city: tenant.config.city || '',
      domain: tenant.config.domain || '',
      extra_services: (form.extraServices && form.extraServices.length > 0)
        ? form.extraServices.map(id => extraServicesOptions.find(o => o.id === id)?.name).join(', ')
        : undefined
    }
    if (props.toEmail) body.toEmail = props.toEmail

    const response = await $fetch<{ success?: boolean; message?: string }>('/api/callback', {
      method: 'POST',
      body
    })

    if (response?.success) {
      submitSuccess.value = true
      form.name = ''
      form.phone = ''
      form.agree = false
      formErrors.name = ''
      formErrors.phone = ''
      setTimeout(() => {
        submitSuccess.value = false
        isModalOpen.value = false
      }, 2000)
    } else {
      submitError.value = (response as any)?.message || 'Ошибка отправки'
    }
  } catch (e: any) {
    submitError.value = e?.data?.message || e?.message || 'Ошибка отправки. Попробуйте позже.'
  } finally {
    isLoading.value = false
  }
}

function closeModal() {
  if (!isLoading.value) {
    submitSuccess.value = false
    submitError.value = ''
    isModalOpen.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isModalOpen"
         class="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-300"
         @click.self="closeModal">
      <div class="absolute inset-0 overflow-y-auto flex items-center justify-center p-4">
        <div class="bg-white rounded-[2rem] md:rounded-[4rem] shadow-2xl w-full max-w-lg relative transform animate-in zoom-in-95 duration-500 my-auto">
          <button type="button"
                  @click="closeModal"
                  class="absolute top-6 right-6 md:top-10 md:right-10 text-gray-300 hover:text-brand-dark transition-all hover:rotate-90 z-10">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 md:h-10 md:w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <div class="p-8 md:p-16">
            <div v-if="submitSuccess" class="text-center py-6">
              <p class="text-xl font-black text-brand-dark uppercase">Заявка отправлена</p>
              <p class="text-gray-500 text-sm mt-2">Перезвоним в рабочее время: {{ workingHoursText }}.</p>
            </div>
            <template v-else>
              <div class="mb-6 md:mb-8">
                <h3 class="text-2xl md:text-3xl font-black text-brand-dark mb-2 uppercase tracking-tighter leading-tight">Заказать обратный звонок</h3>
                <p class="text-gray-400 font-medium text-sm">Оставьте имя и телефон — перезвоним</p>
              </div>

              <form @submit.prevent="handleSubmit" class="space-y-5 md:space-y-6">
                <div class="space-y-2">
                  <label class="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-4">Имя</label>
                  <input v-model="form.name"
                         type="text"
                         required
                         placeholder="Иван Иванов"
                         :class="[
                           'w-full bg-gray-50 border-2 focus:border-brand-blue focus:bg-white rounded-2xl px-6 py-4 outline-none transition-all font-bold text-sm shadow-inner',
                           formErrors.name ? 'border-red-500 focus:border-red-500' : 'border-transparent'
                         ]" />
                  <p v-if="formErrors.name" class="text-red-500 text-xs font-bold ml-4">{{ formErrors.name }}</p>
                </div>
                <div class="space-y-2">
                  <label class="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] ml-4">Телефон</label>
                  <input :value="form.phone"
                         type="tel"
                         inputmode="tel"
                         autocomplete="tel"
                         required
                         placeholder="+7 (___) ___-__-__"
                         maxlength="18"
                         @keydown="onPhoneKeydown"
                         @input="onPhoneInput"
                         :class="[
                           'w-full bg-gray-50 border-2 focus:border-brand-blue focus:bg-white rounded-2xl px-6 py-4 outline-none transition-all font-bold text-sm shadow-inner',
                           formErrors.phone ? 'border-red-500 focus:border-red-500' : 'border-transparent'
                         ]" />
                  <p v-if="formErrors.phone" class="text-red-500 text-xs font-bold ml-4">{{ formErrors.phone }}</p>
                </div>

                <label class="flex items-center gap-4 cursor-pointer group p-2">
                  <div class="relative flex items-center">
                    <input type="checkbox" v-model="form.showExtras" class="peer appearance-none w-6 h-6 border-2 border-gray-100 rounded-xl transition-all shadow-sm" :style="{ backgroundColor: form.showExtras ? brandPrimary : 'transparent', borderColor: form.showExtras ? brandPrimary : '#f3f4f6' }" />
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 absolute left-1 text-white opacity-0 peer-checked:opacity-100 transition-all scale-50 peer-checked:scale-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="4" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span class="text-[9px] md:text-[10px] text-gray-400 font-black leading-tight uppercase tracking-widest group-hover:text-gray-600 transition-colors">
                    Меня также интересуют окна, балконы, потолки или жалюзи <span :style="{ color: brandPrimary }">(отметьте, чтобы получить скидку 10% на эти услуги)</span>
                  </span>
                </label>

                <transition name="fade-slide">
                  <div v-if="form.showExtras" class="grid grid-cols-2 sm:grid-cols-3 gap-3 p-1">
                    <button v-for="service in extraServicesOptions" :key="service.id"
                            type="button"
                            @click="toggleExtraService(service.id)"
                            :class="[
                              'flex flex-col items-center justify-center gap-2 p-3 rounded-2xl border-2 transition-all text-[9px] font-black uppercase tracking-wider',
                              form.extraServices.includes(service.id)
                                ? 'bg-white shadow-xl scale-[1.05]'
                                : 'bg-gray-50/50 border-gray-100 text-gray-400 hover:border-gray-200'
                            ]"
                            :style="form.extraServices.includes(service.id) ? { borderColor: brandPrimary, color: brandPrimary } : {}">
                      <span class="flex items-center justify-center scale-75" v-html="service.icon"></span>
                      <span class="text-center leading-tight">{{ service.name }}</span>
                    </button>
                  </div>
                </transition>

                <label class="flex items-start gap-4 cursor-pointer group p-1">
                  <div class="relative flex items-center mt-1">
                    <input type="checkbox"
                           v-model="form.agree"
                           class="peer appearance-none w-6 h-6 border-2 border-gray-100 rounded-lg md:rounded-xl checked:border-transparent transition-all shadow-sm"
                           :style="{ backgroundColor: form.agree ? brandPrimary : 'transparent', borderColor: form.agree ? brandPrimary : '#f3f4f6' }" />
                    <svg xmlns="http://www.w3.org/2000/svg"
                         class="h-4 w-4 absolute left-1 text-white opacity-0 peer-checked:opacity-100 transition-all scale-50 peer-checked:scale-100"
                         fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="4" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span class="text-[9px] md:text-[10px] text-gray-400 font-black leading-relaxed uppercase tracking-widest group-hover:text-gray-600 transition-colors">
                    Я даю согласие на обработку персональных данных в соответствии с
                    <NuxtLink :to="privacyPolicyUrl" class="underline decoration-2 underline-offset-4" :style="{ color: brandPrimary }" target="_blank">Политикой конфиденциальности</NuxtLink>
                  </span>
                </label>

                <p v-if="submitError" class="text-red-500 text-xs font-bold ml-4">{{ submitError }}</p>

                <button type="submit"
                        :disabled="!form.agree || isLoading"
                        class="w-full font-black py-5 rounded-2xl transition-all shadow-2xl active:scale-95 uppercase text-[10px] md:text-xs tracking-[0.3em] mt-2"
                        :class="[
                          form.agree && !isLoading ? 'text-white' : 'bg-gray-100 text-gray-300 cursor-not-allowed shadow-none'
                        ]"
                        :style="form.agree && !isLoading ? { backgroundColor: brandPrimary, boxShadow: `0 20px 50px -10px ${brandPrimary}66` } : {}">
                  {{ isLoading ? 'Отправка…' : 'Заказать звонок' }}
                </button>
              </form>
            </template>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* Fix for hover on buttons with dynamic colors */
button:not([disabled]):not(.text-white):hover {
  opacity: 0.9;
}

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
</style>
