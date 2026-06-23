<script setup lang="ts">
import punycode from 'punycode'

const tenant = useTenantStore()
const requestURL = import.meta.server ? useRequestURL() : null

const title = computed(() => `Политика конфиденциальности — ${tenant.config.dealer_name || 'Сетки 21'}`)
const description = computed(() => `Политика обработки персональных данных компании ${tenant.config.dealer_name || 'Сетки 21'}. Информация о защите персональных данных клиентов.`)
const unicodeOrigin = useUnicodeOrigin()
const url = computed(() => {
  const origin = unicodeOrigin || 'https://www.setki21.ru'
  return `${origin}/privacy/`
})
const domain = computed(() => {
  if (import.meta.client) {
    const host = window.location.hostname
    try {
      // Декодируем punycode (xn--...) в кириллицу
      return punycode.toUnicode(host)
    } catch (e) {
      return host
    }
  }
  return requestURL?.host || 'setki21.ru'
})

useHead({
  title: title.value,
  meta: [
    { name: 'description', content: description.value },
    { name: 'robots', content: 'index, follow' },
    { property: 'og:title', content: title.value },
    { property: 'og:description', content: description.value },
    { property: 'og:url', content: url.value },
  ],
  link: [
    { rel: 'canonical', href: url.value, key: 'canonical' }
  ],
  script: [
    {
      type: 'application/ld+json',
      children: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "Политика конфиденциальности",
        "description": `Политика обработки персональных данных компании ${tenant.config.dealer_name || 'Сетки 21'}`,
        "publisher": {
          "@type": "Organization",
          "name": tenant.config.dealer_name || 'Сетки 21',
          "address": {
            "@type": "PostalAddress",
            "addressLocality": tenant.config.city || "Чебоксары",
            "addressRegion": tenant.config.city?.includes('Чебоксары') ? "Чувашская Республика" : ""
          }
        }
      })
    }
  ]
})
</script>

<template>
  <div class="bg-gray-50 min-h-screen pb-20">
    <!-- Hero Section -->
    <section class="bg-brand-dark text-white py-20 relative overflow-hidden">
      <div class="container mx-auto px-4 relative z-10 text-center">
        <h1 class="text-4xl md:text-6xl font-black mb-6 uppercase tracking-tighter text-white">
          Политика <span :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">конфиденциальности</span>
        </h1>
        <p class="text-xl text-gray-400 max-w-2xl mx-auto font-medium leading-relaxed">
          Мы заботимся о безопасности ваших данных и соблюдаем все требования законодательства РФ.
        </p>
      </div>
      <div class="absolute top-0 right-0 w-[40rem] h-[40rem] bg-brand-blue/10 rounded-full blur-[120px] -mr-[20rem] -mt-[20rem]"></div>
    </section>

    <div class="container mx-auto px-4 -mt-10 relative z-20">
      <div class="bg-white p-10 md:p-16 rounded-[3rem] shadow-xl border border-gray-100">
        <div class="prose prose-blue max-w-none text-gray-600 space-y-12 font-medium text-sm md:text-base">

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">1</span>
              Общие положения
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                1.1. Настоящая Политика оператора в отношении обработки персональных данных (далее – Политика) разработана в целях обеспечения защиты прав и свобод субъектов персональных данных, а также в соответствии с требованиями Федерального закона РФ от 27.07.2006 №152-ФЗ «О персональных данных» и иных нормативных правовых актов.
              </p>
              <p v-if="tenant.config.legal?.requisites">
                1.2. Оператор – {{ tenant.config.legal.requisites.split('\n')[0] }}, реквизиты: {{ tenant.config.legal.requisites.replace(/\n/g, ', ') }}, e-mail: {{ tenant.config.email }}, телефон: {{ tenant.config.phone }}.
              </p>
              <p v-else-if="tenant.config.legal_info?.requisites">
                1.2. Оператор – {{ tenant.config.legal_info.requisites.split('\n')[0] }}, реквизиты: {{ tenant.config.legal_info.requisites.replace(/\n/g, ', ') }}, e-mail: {{ tenant.config.email }}, телефон: {{ tenant.config.phone }}.
              </p>
              <p v-else>
                1.2. Оператор – ООО «Бикос», ИНН 2130053014, ОГРН 1092130000995, юридический адрес: 428005, Чувашская Республика, г. Чебоксары, ул. Гражданская, д. 53, оф. 1, e-mail: info@setki21.ru, телефон: +7 (8352) 38-14-20.
              </p>
              <p>
                1.3. Настоящая Политика применяется ко всей информации, которую Оператор может получить о пользователе во время использования сайта <a :href="url" class="underline notranslate" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">{{ domain }}</a> и его поддоменов, а также при взаимодействии по телефону и электронной почте.
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">2</span>
              Термины и определения
            </h2>
            <ul class="list-none space-y-4 ml-14">
              <li class="flex gap-3">
                <span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span>
                <span><b>Персональные данные</b> — любая информация, относящаяся к прямо или косвенно определенному или определяемому физическому лицу (например, ФИО, e-mail, телефон, адрес).</span>
              </li>
              <li class="flex gap-3">
                <span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span>
                <span><b>Обработка персональных данных</b> — любое действие (операция) или совокупность действий, совершаемых с персональными данными с использованием или без использования средств автоматизации (сбор, запись, систематизация, накопление, хранение, уточнение, использование, передача, обезличивание, блокирование, удаление, уничтожение).</span>
              </li>
              <li class="flex gap-3">
                <span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span>
                <span><b>Оператор</b> — лицо (организация), самостоятельно или совместно с другими лицами организующее и (или) осуществляющее обработку персональных данных.</span>
              </li>
              <li class="flex gap-3">
                <span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span>
                <span><b>Пользователь (Субъект персональных данных)</b> — физическое лицо, к которому относятся персональные данные.</span>
              </li>
            </ul>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">3</span>
              Категории и источники персональных данных
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                3.1. Оператор обрабатывает следующие категории персональных данных: фамилия, имя, отчество (ФИО); контактный телефон; адрес электронной почты; адрес доставки; иные сведения, предоставляемые пользователем через формы на сайте, по телефону или по электронной почте.
              </p>
              <p>
                3.2. Персональные данные поступают оператору от самого пользователя (через заполнение форм на сайте, отправку заявок по электронной почте, телефонные обращения и т.д.).
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">4</span>
              Цели, правовые основания и условия обработки
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                4.1. Оператор обрабатывает персональные данные пользователей исключительно в целях:
              </p>
              <ul class="list-none space-y-2">
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> оформления и исполнения заказов;</li>
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> предоставления информации об услугах;</li>
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> обратной связи, обработки обращений;</li>
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> направления информации, в том числе рекламного характера (по согласованию);</li>
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> исполнения требований законодательства.</li>
              </ul>
              <p>
                4.2. Правовым основанием обработки персональных данных является согласие пользователя, договор с пользователем или иное основание, предусмотренное законодательством РФ.
              </p>
              <p>
                4.3. Персональные данные обрабатываются с соблюдением принципов и условий, предусмотренных действующим законодательством РФ.
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">5</span>
              Способы обработки, e-mail и телефон
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                5.1. Обработка персональных данных осуществляется с использованием средств автоматизации (через сайт, почтовые сервисы, CRM и т.п.) и без таковых (например, обработка поступающих по телефону обращений).
              </p>
              <p>
                5.2. Оператор использует электронную почту и телефон для приема, хранения и обработки заявок, вопросов и иной информации от пользователей. Доступ к этим каналам имеют только уполномоченные сотрудники, реализованы организационные и технические меры защиты (пароли, антивирус, ограничение доступа, шифрование каналов, контроль хранения и удаления писем/сообщений).
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">6</span>
              Передача и раскрытие персональных данных третьим лицам
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                6.1. Оператор может передавать персональные данные только:
              </p>
              <ul class="list-none space-y-2">
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> государственным органам в случаях, предусмотренных законом;</li>
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> партнерам, участвующим в исполнении заказа (например, доставка);</li>
                <li class="flex gap-3"><span class="text-brand-blue font-black" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">•</span> иным лицам — только с согласия пользователя.</li>
              </ul>
              <p>
                6.2. Передача данных за пределы РФ не осуществляется, за исключением случаев, прямо предусмотренных законодательством.
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">7</span>
              Меры по обеспечению безопасности
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                7.1. Оператор принимает необходимые правовые, организационные и технические меры для защиты персональных данных от неправомерного или случайного доступа, уничтожения, изменения, блокирования, копирования, распространения, а также от иных неправомерных действий.
              </p>
              <p>
                7.2. Доступ к персональным данным ограничен; используется система паролей, двухфакторная аутентификация, антивирус, регулярное резервное копирование; доступ имеют только уполномоченные лица.
              </p>
              <p>
                7.3. Вся обработка персональных данных по e-mail и телефону осуществляется только уполномоченными сотрудниками, на защищенных устройствах/почтовых сервисах с сильными паролями.
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">8</span>
              Сроки хранения и уничтожения
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                8.1. Персональные данные хранятся не дольше, чем это необходимо для целей их обработки, либо в течение срока, установленного законодательством РФ.
              </p>
              <p>
                8.2. По достижении целей обработки, а также по требованию субъекта персональных данных, данные подлежат уничтожению или обезличиванию, если иное не предусмотрено законом.
              </p>
              <p>
                8.3. Согласие на обработку персональных данных хранится 3 года с момента окончания его действия.
              </p>
            </div>
          </div>

          <div class="section">
            <h2 class="text-2xl font-black text-brand-dark uppercase tracking-wider mb-6 flex items-center gap-4">
              <span class="w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg shrink-0" :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2' }">9</span>
              Права субъекта персональных данных
            </h2>
            <div class="space-y-4 ml-14">
              <p>
                9.1. Пользователь вправе получать информацию об обработке своих персональных данных, требовать их уточнения, блокирования или уничтожения в случаях, если данные являются неполными, устаревшими, неточными или незаконно полученными.
              </p>
              <p>
                9.2. Для реализации своих прав пользователь может направить запрос по электронной почте: <a :href="`mailto:${tenant.config.email || 'info@setki21.ru'}`" class="underline" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">{{ tenant.config.email || 'info@setki21.ru' }}</a>.
              </p>
              <p>
                9.3. Запросы рассматриваются в срок не более 30 дней с момента поступления.
              </p>
              <p>
                9.4. Пользователь вправе отозвать согласие на обработку персональных данных.
              </p>
            </div>
          </div>

          <div class="section bg-gray-50 p-10 rounded-[2rem] border border-gray-100">
            <h2 class="text-xl font-black text-brand-dark uppercase tracking-wider mb-6">10. Контактные данные оператора</h2>
            <div v-if="tenant.config.legal?.requisites" class="text-sm leading-relaxed whitespace-pre-line font-bold text-gray-700">
              {{ tenant.config.legal.requisites }}<br>
              Телефон: {{ tenant.config.phone }}<br>
              E-mail: <a :href="`mailto:${tenant.config.email}`" class="underline" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">{{ tenant.config.email }}</a>
            </div>
            <div v-else-if="tenant.config.legal_info?.requisites" class="text-sm leading-relaxed whitespace-pre-line font-bold text-gray-700">
              {{ tenant.config.legal_info.requisites }}<br>
              Телефон: {{ tenant.config.phone }}<br>
              E-mail: <a :href="`mailto:${tenant.config.email}`" class="underline" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">{{ tenant.config.email }}</a>
            </div>
            <p v-else class="text-sm leading-relaxed font-bold text-gray-700">
              ООО «Бикос»<br>
              Юридический адрес: 428005, Чувашская Республика, г. Чебоксары, ул. Гражданская, д. 53, оф. 1<br>
              ИНН: 2130053014<br>
              ОГРН: 1092130000995<br>
              Ответственный: Кондратьев И.В.<br>
              Телефон: +7 (8352) 38-14-20<br>
              E-mail: <a href="mailto:info@setki21.ru" class="underline" :style="{ color: tenant.config.branding?.primary_color || '#2A6AB2' }">info@setki21.ru</a>
            </p>
            <p class="mt-6 text-xs text-gray-400 italic">
              Действующая редакция Политики опубликована на сайте <span class="notranslate">{{ domain }}</span>. Оператор вправе вносить изменения в настоящую Политику.
            </p>
          </div>
        </div>

        <div class="mt-16 text-center">
          <NuxtLink to="/" class="inline-flex items-center gap-3 text-white px-10 py-5 rounded-2xl font-black text-xs uppercase tracking-[0.2em] transition-all shadow-xl active:scale-95 hover:opacity-90"
                    :style="{ backgroundColor: tenant.config.branding?.primary_color || '#2A6AB2', boxShadow: `0 20px 50px -10px ${(tenant.config.branding?.primary_color || '#2A6AB2')}66` }">
            ← На главную
          </NuxtLink>
        </div>
      </div>
    </div>
  </div>
</template>
