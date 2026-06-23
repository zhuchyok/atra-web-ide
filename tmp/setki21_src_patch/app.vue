<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useTenantStore } from '~/stores/tenant'
import { usePricingStore } from '~/stores/pricing'
import { useOrderStore } from '~/stores/order'

const auth = useAuthStore()
const tenant = useTenantStore()
const pricing = usePricingStore()
const route = useRoute()

// Конфиг тенанта: на SSR — по Host из запроса
const event = import.meta.server ? useRequestEvent() : null
const headers = event?.node?.req?.headers
const ssrHost = (headers?.['x-forwarded-host'] as string) || headers?.host
const ssrProto = (headers?.['x-forwarded-proto'] as string) || (process.env.NODE_ENV === 'production' ? 'https' : 'http')
const ssrOrigin = ssrHost ? `${ssrProto}://${ssrHost}` : undefined

const requestURL = useRequestURL()
const siteOrigin = (import.meta.server && ssrOrigin) ? ssrOrigin : (requestURL?.origin || '')

const finalSiteOrigin = computed(() => {
  if (process.env.NODE_ENV === 'production' && siteOrigin.startsWith('http://')) {
    return siteOrigin.replace('http://', 'https://')
  }
  return siteOrigin
})

const { data: tenantConfig } = await useAsyncData('tenant-config', async () => {
  await tenant.fetchConfig(ssrOrigin)
  return tenant.config
}, {
  watch: [computed(() => ssrOrigin)]
})

const { data: pricingData } = await useAsyncData('pricing-config', async () => {
  await pricing.fetchPricing(true, ssrOrigin)
  const orderStore = useOrderStore()
  // Принудительный расчет на сервере
  orderStore.totalPrice
  return pricing.pricing
})

// Хелпер для локализации текста (замена {city})
const localize = (text: string) => {
  if (!text) return ''
  const city = tenantConfig.value?.city || ''
  return text.replace(/{city}/g, city)
}

const canonicalUrl = computed(() => {
  const origin = finalSiteOrigin.value || 'https://www.setki21.ru'
  const path = route.path.replace(/\/$/, '') || '/'
  return `${origin}${path === '/' ? '' : path}`
})

onMounted(() => {
  auth.initAuth()
  if (import.meta.client) {
    tenant.fetchConfig()
  }
  if (!pricing.pricing) {
    pricing.fetchPricing()
  }
})

useHead({
  title: computed(() => localize(tenantConfig.value?.seo?.title) || 'Москитные сетки в Чебоксарах и Новочебоксарске — Сетки 21'),
  meta: computed(() => {
    const ogImage = tenantConfig.value?.branding?.logo_url || (siteOrigin ? `${siteOrigin}/images/logo_final_v58.png` : 'https://www.setki21.ru/images/logo_final_v58.png')
    const verificationTag = tenantConfig.value?.seo?.verification_tag
    const desc = localize(tenantConfig.value?.seo?.description)
    return [
      { name: 'description', content: desc || '' },
      { property: 'og:title', content: localize(tenantConfig.value?.seo?.title) || '' },
      { property: 'og:description', content: desc || '' },
      { property: 'og:image', content: ogImage },
      { name: 'twitter:image', content: ogImage },
      { name: 'robots', content: 'index, follow' },
      ...(verificationTag ? [{ name: 'yandex-verification', content: verificationTag }] : [])
    ]
  }),
  link: computed(() => {
    const faviconUrl = tenantConfig.value?.branding?.favicon_url || tenantConfig.value?.branding?.logo_url || (siteOrigin ? `${siteOrigin}/favicon.ico` : '/favicon.ico')
    return [
      { rel: 'canonical', href: canonicalUrl.value },
      { rel: 'icon', type: 'image/x-icon', href: faviconUrl },
      { rel: 'shortcut icon', type: 'image/x-icon', href: faviconUrl },
      { rel: 'apple-touch-icon', href: faviconUrl }
    ]
  }),
  script: computed(() => {
    const scripts = []

    if (tenantConfig.value?.seo?.analytics_code) {
      scripts.push({
        innerHTML: tenantConfig.value.seo.analytics_code,
        type: 'text/javascript',
        body: true
      })
    }

    // LocalBusiness JSON-LD
    const branch = tenantConfig.value?.contacts?.branches?.[0]
    if (branch || tenantConfig.value?.city) {
      const localBusiness = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": tenantConfig.value?.dealer_name || "Сетки 21",
        "image": tenantConfig.value?.branding?.logo_url || "https://www.setki21.ru/images/logo_final_v58.png",
        "telephone": tenantConfig.value?.phone || "",
        "address": {
          "@type": "PostalAddress",
          "streetAddress": branch?.address || "",
          "addressLocality": tenantConfig.value?.city || "",
          "addressCountry": "RU"
        },
        "url": finalSiteOrigin.value
      }
      scripts.push({
        type: 'application/ld+json',
        innerHTML: JSON.stringify(localBusiness)
      })
    }

    // FAQPage JSON-LD
    const faq = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": `Где купить москитные сетки в ${tenantConfig.value?.city || 'вашем городе'}?`,
          "acceptedAnswer": {
            "@type": "Answer",
            "text": `Вы можете заказать москитные сетки напрямую у производителя ${tenantConfig.value?.dealer_name || 'Сетки 21'} с доставкой и установкой.`
          }
        },
        {
          "@type": "Question",
          "name": "Сколько стоит изготовление сетки?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Стоимость зависит от размеров и типа полотна. Воспользуйтесь нашим онлайн-калькулятором для точного расчета цены."
          }
        }
      ]
    }
    scripts.push({
      type: 'application/ld+json',
      innerHTML: JSON.stringify(faq)
    })

    return scripts
  })
})
</script>

<template>
  <div
    :class="{ 'opacity-0': !tenant.isLoaded }"
    class="transition-opacity duration-300"
    :style="{ '--brand-primary': tenant.config.branding?.primary_color || '#2A6AB2', '--brand-blue': tenant.config.branding?.primary_color || '#2A6AB2' }"
  >
    <NuxtLayout>
      <NuxtPage :key="$route.fullPath" />
    </NuxtLayout>
  </div>
</template>

<style>
html {
  scroll-behavior: smooth;
}
body {
  margin: 0;
  padding: 0;
  font-family: 'Inter', sans-serif;
  background-color: #ffffff;
  color: #334155;
}
.btn-primary {
  @apply bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-full transition-all shadow-lg;
}
.btn-secondary {
  @apply bg-white border-2 border-blue-600 text-blue-600 hover:bg-blue-600 hover:text-white font-bold py-3 px-6 rounded-full transition-all;
}
</style>
