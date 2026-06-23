import nodemailer from "nodemailer";
import { escapeHtml } from "../utils/escape-html";

/** Нормализация телефона: только цифры, 8 в начале заменяем на 7, ожидаем 11 цифр (РФ). */
function normalizePhone(value: string): string | null {
  const digits = value.replace(/\D/g, "");
  if (digits.length === 0) return null;
  const normalized = digits.startsWith("8")
    ? "7" + digits.slice(1)
    : digits.startsWith("7")
      ? digits
      : "7" + digits;
  return normalized.length === 11 ? normalized : null;
}

export default defineEventHandler(async (event) => {
  // CORS headers
  setHeader(event, "Access-Control-Allow-Origin", "*");
  setHeader(event, "Access-Control-Allow-Methods", "POST, OPTIONS");
  setHeader(event, "Access-Control-Allow-Headers", "Content-Type");

  if (event.method === "OPTIONS") {
    return { status: "ok" };
  }

  try {
    const body = await readBody(event);

    // trim всех строковых полей
    const trimmed = {
      formName: String(body.formName ?? "").trim(),
      formPhone: String(body.formPhone ?? "").trim(),
      formEmail: body.formEmail ? String(body.formEmail).trim() : undefined,
      formAddress: body.formAddress
        ? String(body.formAddress).trim()
        : undefined,
      formComment: body.formComment
        ? String(body.formComment).trim()
        : undefined,
      list_order: String(body.list_order ?? "").trim(),
      total_price_value: body.total_price_value,
      total_order_value: body.total_order_value
        ? String(body.total_order_value).trim()
        : undefined,
      extra_services: body.extra_services
        ? String(body.extra_services).trim()
        : undefined,
      measurement: body.measurement,
      discount_type: body.discount_type,
      dealer_id:
        body.dealer_id &&
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          body.dealer_id,
        )
          ? body.dealer_id
          : undefined,
      branch_id:
        body.branch_id &&
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          body.branch_id,
        )
          ? body.branch_id
          : undefined,
      items: Array.isArray(body.items) ? body.items : [],
    };

    const phoneNorm = normalizePhone(trimmed.formPhone);
    if (!phoneNorm) {
      throw createError({
        statusCode: 400,
        statusMessage:
          "Неверный формат телефона. Введите 11 цифр, например +7 (927) 858-88-88",
      });
    }

    // 1. Сохранение в БД через moskit-api
    let orderIdFromDb = Date.now();
    let orderNumberFromDb = `WEB-${orderIdFromDb}`;
    let dealerData: any = null;

    try {
      const apiUrl = process.env.API_URL || "http://setki21-api-new:8080";
      const cleanApiUrl = apiUrl.endsWith("/") ? apiUrl.slice(0, -1) : apiUrl;

      // Получаем данные дилера для письма (город, название)
      if (trimmed.dealer_id) {
        try {
          dealerData = await $fetch(`${cleanApiUrl}/api/v1/tenant/config`, {
            headers: { host: getHeader(event, "host") || "" },
            query: { dealer_id: trimmed.dealer_id },
          });
        } catch (e) {
          console.error("Failed to fetch dealer info for email:", e);
        }
      }

      const orderPayload = {
        client_name: trimmed.formName,
        client_phone: phoneNorm,
        client_address: trimmed.formAddress,
        dealer_id: trimmed.dealer_id,
        branch_id: trimmed.branch_id || null,
        items: trimmed.items.map((item: any) => {
          let productId = "00000000-0000-0000-0000-000000000004";
          const meshType = item.params?.mesh_type || "";
          if (meshType === "antikoshka")
            productId = "00000000-0000-0000-0000-000000000005";
          return {
            product_id: productId,
            name: item.name,
            quantity: item.quantity,
            price: item.price,
            params: item.params,
          };
        }),
      };

      const dbResponse: any = await $fetch(
        `${cleanApiUrl}/api/v1/dealer/orders`,
        {
          method: "POST",
          body: orderPayload,
        },
      );

      if (dbResponse && dbResponse.order_id) {
        orderIdFromDb = dbResponse.order_id;
        orderNumberFromDb = dbResponse.order_number || orderNumberFromDb;
      }
    } catch (dbError: any) {
      console.error("CRITICAL: Failed to save order to DB:", dbError);
      const remoteMessage = dbError.data?.message || dbError.message;
      const isBusinessError =
        dbError.statusCode === 400 || dbError.statusCode === 422;
      throw createError({
        statusCode: isBusinessError ? 400 : 503,
        statusMessage: isBusinessError
          ? remoteMessage
          : "Сервис временно недоступен.",
      });
    }

    // 2. Настройка SMTP
    const smtpPort = parseInt(process.env.SMTP_PORT || "465", 10);
    const transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || "smtp.timeweb.ru",
      port: smtpPort,
      secure: smtpPort === 465,
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
      },
    });

    const city = dealerData?.city || "Чебоксары";
    const dealerName = dealerData?.dealer_name || "Сетки 21";
    const brandColor = dealerData?.branding?.primary_color || "#2A6AB2";

    // Формируем состав заказа и итог для письма только из items (контур, который уходит в БД),
    // чтобы email и админка показывали одинаковую цену.
    const normalizedItems = trimmed.items.map((item: any) => {
      const quantity = Number(item?.quantity ?? 1);
      const unitPrice = Number(item?.price ?? 0);
      const params = item?.params || {};
      const width = Number(params?.width ?? 0);
      const height = Number(params?.height ?? 0);
      const color = params?.color ? String(params.color) : "";
      const frame = params?.frame_type ? String(params.frame_type) : "";
      const mesh = params?.mesh_type ? String(params.mesh_type) : "";
      const measurementMethod = params?.measurement_method
        ? String(params.measurement_method)
        : "";
      const handleType = params?.handle_type ? String(params.handle_type) : "";
      const installation =
        typeof params?.installation === "boolean" ? params.installation : false;

      return {
        name: String(item?.name || "СЕТКА"),
        quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
        unitPrice: Number.isFinite(unitPrice) && unitPrice >= 0 ? unitPrice : 0,
        width: Number.isFinite(width) && width > 0 ? width : 0,
        height: Number.isFinite(height) && height > 0 ? height : 0,
        color,
        frame,
        mesh,
        measurementMethod,
        handleType,
        installation,
      };
    });

    const orderLinesHtml =
      normalizedItems.length > 0
        ? normalizedItems
            .map((item) => {
              const sizePart =
                item.width > 0 && item.height > 0
                  ? `${item.width}x${item.height}`
                  : "РАЗМЕР НЕ УКАЗАН";
              const framePart = item.frame ? `${item.frame}: ` : "";
              const meshPart = item.mesh ? `${item.mesh.toUpperCase()} ` : "";
              const colorPart = item.color || "БЕЗ ЦВЕТА";
              const handlePart = item.handleType
                ? `, РУЧКИ: ${item.handleType.toUpperCase()}`
                : "";
              const installPart = item.installation
                ? ", МОНТАЖ: ДА"
                : ", МОНТАЖ: НЕТ";
              const measurePart = item.measurementMethod
                ? `, ЗАМЕР: ${item.measurementMethod}`
                : "";
              const line = `${framePart}${meshPart}(${sizePart}, ${colorPart}${handlePart}${installPart}${measurePart}) - ${item.quantity} шт`;
              return `<div style="padding: 8px 0; border-bottom: 1px solid #f3f4f6;">${escapeHtml(line)}</div>`;
            })
            .join("")
        : '<div style="padding: 8px 0;">СОСТАВ ЗАКАЗА НЕ ПЕРЕДАН</div>';

    const emailTotal = normalizedItems.reduce(
      (sum, item) => sum + item.unitPrice * item.quantity,
      0,
    );

    const htmlContent = `
      <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #f9fafb; padding: 40px 20px;">
        <div style="background-color: #ffffff; border-radius: 24px; overflow: hidden; shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);">
          <!-- Header -->
          <div style="background-color: ${brandColor}; padding: 30px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 24px; text-transform: uppercase; letter-spacing: 1px;">Новый заказ №${orderNumberFromDb}</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0; font-size: 14px; font-weight: bold; text-transform: uppercase;">${dealerName} — ${city}</p>
          </div>

          <div style="padding: 30px;">
            <!-- Клиент -->
            <div style="margin-bottom: 30px;">
              <h3 style="color: #9ca3af; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 15px; font-weight: 900;">Данные клиента</h3>
              <div style="background-color: #f3f4f6; border-radius: 16px; padding: 20px;">
                <p style="margin: 0 0 10px 0; font-size: 16px;"><strong>Имя:</strong> ${escapeHtml(trimmed.formName)}</p>
                <p style="margin: 0 0 10px 0; font-size: 16px;"><strong>Телефон:</strong> <a href="tel:${phoneNorm}" style="color: ${brandColor}; text-decoration: none; font-weight: bold;">${escapeHtml(trimmed.formPhone)}</a></p>
                ${trimmed.formAddress ? `<p style="margin: 0; font-size: 16px;"><strong>Адрес:</strong> ${escapeHtml(trimmed.formAddress)}</p>` : ""}
              </div>
            </div>

            <!-- Заказ -->
            <div style="margin-bottom: 30px;">
              <h3 style="color: #9ca3af; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 15px; font-weight: 900;">Состав заказа</h3>
              <div style="border: 2px solid #f3f4f6; border-radius: 16px; padding: 20px;">
                <div style="font-size: 14px; line-height: 1.6; color: #374151;">
                  ${orderLinesHtml}
                </div>
                <div style="margin-top: 20px; text-align: right;">
                  <span style="color: #9ca3af; font-size: 12px; text-transform: uppercase; font-weight: bold;">Итого к оплате:</span>
                  <div style="color: ${brandColor}; font-size: 32px; font-weight: 900; margin-top: 5px;">${emailTotal.toLocaleString("ru-RU")} ₽</div>
                </div>
              </div>
            </div>

            <!-- Доп. услуги -->
            <div style="margin-bottom: 30px;">
              <h3 style="color: #9ca3af; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 15px; font-weight: 900;">Дополнительно</h3>
              <div style="background-color: ${brandColor}0D; border: 1px solid ${brandColor}1A; border-radius: 16px; padding: 20px; color: ${brandColor};">
                <p style="margin: 0 0 8px 0; font-size: 14px; font-weight: bold;">
                  <span style="opacity: 0.7;">📦 Способ получения:</span> ${escapeHtml(trimmed.total_order_value || "Не указан")}
                </p>
                ${
                  trimmed.measurement
                    ? `<p style="margin: 0 0 8px 0; font-size: 14px; font-weight: bold;"><span style="opacity: 0.7;">📏 Замер:</span> Требуется выезд мастера (${city})</p>`
                    : `<p style="margin: 0 0 8px 0; font-size: 14px; font-weight: bold;"><span style="opacity: 0.7;">📏 Замер:</span> Своими силами (см. детали в составе заказа)</p>`
                }
                ${trimmed.discount_type === "srochnyi" ? `<p style="margin: 0; font-size: 14px; font-weight: bold;"><span style="opacity: 0.7;">⚡ Срочность:</span> Приоритетный заказ (+400 ₽)</p>` : ""}
                ${trimmed.extra_services ? `<p style="margin: 8px 0 0 0; font-size: 14px; font-weight: bold;"><span style="opacity: 0.7;">Также интересует:</span> ${escapeHtml(trimmed.extra_services)}</p>` : ""}
              </div>
            </div>

            ${
              trimmed.formComment
                ? `
            <div>
              <h3 style="color: #9ca3af; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 15px; font-weight: 900;">Комментарий</h3>
              <div style="font-style: italic; color: #6b7280; font-size: 14px; background-color: #f9fafb; padding: 15px; border-radius: 12px; border-left: 4px solid #d1d5db;">
                ${escapeHtml(trimmed.formComment)}
              </div>
            </div>`
                : ""
            }
          </div>

          <!-- Footer -->
          <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #f3f4f6;">
            <p style="color: #9ca3af; font-size: 11px; margin: 0; text-transform: uppercase; letter-spacing: 1px;">
              Заказ создан через сайт ${dealerName}<br>
              ${new Date().toLocaleString("ru-RU")}
            </p>
          </div>
        </div>
      </div>
    `;

    // Отправка email
    // Приоритет: email дилера из базы данных (dealerData) -> email из тела запроса -> email из окружения -> дефолт
    const recipientEmail =
      dealerData?.email ||
      body.dealer_email ||
      body.formDealerEmail ||
      process.env.ORDER_EMAIL ||
      "info@setki21.ru";

    try {
      await transporter.sendMail({
        from: `"${dealerName}" <${process.env.SMTP_USER}>`,
        to: recipientEmail,
        subject: `Заказ №${orderNumberFromDb} (${city}) - ${trimmed.formName}`,
        html: htmlContent,
        replyTo: trimmed.formEmail || phoneNorm,
      });
    } catch (mailError) {
      console.error("NON-CRITICAL: Failed to send order email:", mailError);
    }

    return {
      success: true,
      message: "Заказ успешно отправлен!",
      orderId: orderIdFromDb,
      orderNumber: orderNumberFromDb,
    };
  } catch (error: any) {
    console.error("Order API error:", error);
    throw createError({
      statusCode: error.statusCode || 500,
      statusMessage: error.statusMessage || "Internal server error",
    });
  }
});
