use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;
use tracing;

#[derive(Debug, Serialize, Deserialize)]
struct TokenResponse {
    token: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct ProxyHostResponse {
    id: i64,
}

#[derive(Debug, Serialize, Deserialize)]
struct CertificateResponse {
    id: i64,
}

pub struct NpmClient {
    client: Client,
    base_url: String,
    identity: String,
    secret: String,
    /// Хост для Custom Locations (/api, /health, /uploads). На VDS: setki21-api-new.
    forward_api_host: String,
}

impl NpmClient {
    pub fn new() -> Self {
        let base_url =
            env::var("NPM_URL").unwrap_or_else(|_| "http://atra-nginx-proxy:81/api".to_string());
        let identity =
            env::var("NPM_IDENTITY").unwrap_or_else(|_| "zhuchyok@icloud.com".to_string());
        let secret = env::var("NPM_SECRET").unwrap_or_else(|_| "Bik6007OS".to_string());
        let forward_api_host =
            env::var("NPM_FORWARD_API_HOST").unwrap_or_else(|_| "setki21-api-new".to_string());

        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(60)) // Увеличен таймаут для SSL-запросов
            .build()
            .unwrap_or_else(|_| Client::new());
        Self {
            client,
            base_url,
            identity,
            secret,
            forward_api_host,
        }
    }

    async fn get_token(&self) -> Result<String, String> {
        let url = format!("{}/tokens", self.base_url);
        let resp = self
            .client
            .post(&url)
            .json(&json!({
                "identity": self.identity,
                "secret": self.secret
            }))
            .send()
            .await
            .map_err(|e| format!("NPM Auth request failed: {}", e))?;

        let status = resp.status();
        if !status.is_success() {
            let err_text = resp.text().await.unwrap_or_default();
            return Err(format!("NPM Auth failed: {} - {}", status, err_text));
        }

        let data: TokenResponse = resp
            .json()
            .await
            .map_err(|e| format!("NPM Auth JSON error: {}", e))?;

        Ok(data.token)
    }

    async fn find_proxy_host_by_domain(&self, domain: &str) -> Result<Option<i64>, String> {
        let token = self.get_token().await?;
        let url = format!("{}/nginx/proxy-hosts", self.base_url);

        let resp = self
            .client
            .get(&url)
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await
            .map_err(|e| format!("NPM List Hosts request failed: {}", e))?;

        if !resp.status().is_success() {
            return Err(format!("NPM List Hosts failed: {}", resp.status()));
        }

        let hosts: Vec<serde_json::Value> = resp
            .json()
            .await
            .map_err(|e| format!("NPM List Hosts JSON error: {}", e))?;

        // Ищем хост, у которого в domain_names есть наш домен
        for host in hosts {
            if let Some(domain_names) = host["domain_names"].as_array() {
                for dn in domain_names {
                    if let Some(dn_str) = dn.as_str() {
                        if dn_str == domain {
                            if let Some(id) = host["id"].as_i64() {
                                return Ok(Some(id));
                            }
                        }
                    }
                }
            }
        }
        Ok(None)
    }

    /// Запрос SSL-сертификата от Let's Encrypt для указанных доменов
    async fn request_ssl_certificate(&self, domain_names: Vec<String>) -> Result<i64, String> {
        let token = self.get_token().await?;
        let url = format!("{}/nginx/certificates", self.base_url);

        tracing::info!(
            "Requesting Let's Encrypt SSL certificate for domains: {:?}",
            domain_names
        );

        let payload = json!({
            "provider": "letsencrypt",
            "domain_names": domain_names
        });

        let resp = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {}", token))
            .json(&payload)
            .send()
            .await
            .map_err(|e| format!("NPM Request SSL failed: {}", e))?;

        let status = resp.status();
        if !status.is_success() {
            let err_text = resp.text().await.unwrap_or_default();
            tracing::error!("NPM SSL request failed: {} - {}", status, err_text);
            return Err(format!("NPM SSL request failed: {} - {}", status, err_text));
        }

        let cert_data: CertificateResponse = resp
            .json()
            .await
            .map_err(|e| format!("NPM SSL JSON error: {}", e))?;

        tracing::info!(
            "Successfully obtained SSL certificate, ID: {}",
            cert_data.id
        );
        Ok(cert_data.id)
    }

    /// Обновление Proxy Host для привязки SSL-сертификата
    async fn update_proxy_host_certificate(
        &self,
        proxy_host_id: i64,
        certificate_id: i64,
    ) -> Result<(), String> {
        let token = self.get_token().await?;
        let url = format!("{}/nginx/proxy-hosts/{}", self.base_url, proxy_host_id);

        tracing::info!(
            "Updating Proxy Host {} with certificate {}",
            proxy_host_id,
            certificate_id
        );

        // Получаем текущую конфигурацию хоста
        let resp = self
            .client
            .get(&url)
            .header("Authorization", format!("Bearer {}", token))
            .send()
            .await
            .map_err(|e| format!("NPM Get Host failed: {}", e))?;

        if !resp.status().is_success() {
            return Err(format!("NPM Get Host failed: {}", resp.status()));
        }

        let mut host_config: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| format!("NPM Get Host JSON error: {}", e))?;

        // Для PUT NPM ожидает только изменяемые поля, без created_on/owner_user_id/id.
        let payload = json!({
            "domain_names": host_config["domain_names"],
            "forward_scheme": host_config["forward_scheme"],
            "forward_host": host_config["forward_host"],
            "forward_port": host_config["forward_port"],
            "access_list_id": host_config["access_list_id"],
            "certificate_id": certificate_id,
            "ssl_forced": true,
            "caching_enabled": host_config["caching_enabled"],
            "block_exploits": host_config["block_exploits"],
            "advanced_config": host_config["advanced_config"],
            "allow_websocket_upgrade": host_config["allow_websocket_upgrade"],
            "http2_support": true,
            "enabled": host_config["enabled"],
            "locations": host_config["locations"],
            "hsts_enabled": true,
            "hsts_subdomains": false,
            "trust_forwarded_proto": host_config["trust_forwarded_proto"]
        });

        // Отправляем обновлённую конфигурацию
        let resp = self
            .client
            .put(&url)
            .header("Authorization", format!("Bearer {}", token))
            .json(&payload)
            .send()
            .await
            .map_err(|e| format!("NPM Update Host Certificate failed: {}", e))?;

        let status = resp.status();
        if !status.is_success() {
            let err_text = resp.text().await.unwrap_or_default();
            tracing::error!(
                "NPM Update Host Certificate failed: {} - {}",
                status,
                err_text
            );
            return Err(format!(
                "NPM Update Host Certificate failed: {} - {}",
                status, err_text
            ));
        }

        tracing::info!(
            "Successfully updated Proxy Host {} with certificate {}",
            proxy_host_id,
            certificate_id
        );
        Ok(())
    }

    pub async fn create_proxy_host(&self, domain: &str) -> Result<i64, String> {
        // NPM/Certbot не поддерживают IDN (кириллица, .рф) — передаём домен в Punycode
        let domain_ascii = idna::domain_to_ascii(domain.trim())
            .map_err(|e| format!("Invalid domain (IDN conversion failed): {}", e))?;
        if domain_ascii != domain.trim() {
            tracing::info!(
                "Domain {} sent to NPM as punycode: {}",
                domain,
                domain_ascii
            );
        }

        let token = self.get_token().await?;

        // Конфигурация для Сетки 21: default — setki21-site (сайт), Custom Locations — setki21-api-new (API + uploads)
        let loc_host = &self.forward_api_host;

        // Автоматически добавляем домен с www и без (если нет www — добавляем, если есть — добавляем версию без)
        let domain_with_www = if domain_ascii.starts_with("www.") {
            domain_ascii.to_string()
        } else {
            format!("www.{}", domain_ascii)
        };
        let domain_without_www = domain_ascii
            .strip_prefix("www.")
            .unwrap_or(&domain_ascii)
            .to_string();

        let domain_names = vec![domain_without_www.clone(), domain_with_www.clone()];

        let payload = json!({
            "domain_names": domain_names.clone(),
            "forward_scheme": "http",
            "forward_host": "setki21-web-new",
            "forward_port": 3000,
            "access_list_id": 0,
            "certificate_id": 0, // Сначала создаём без сертификата
            "ssl_forced": false, // Включим после получения сертификата
            "caching_enabled": false,
            "block_exploits": true,
            "hsts_enabled": false, // Включим после получения сертификата
            "hsts_subdomains": false,
            "advanced_config": "",
            "meta": {
                "letsencrypt_email": self.identity,
                "letsencrypt_agree": true,
                "dns_challenge": false
            },
            "locations": [
                { "path": "/api",     "forward_scheme": "http", "forward_host": loc_host, "forward_port": 8080, "advanced_config": "" },
                { "path": "/health", "forward_scheme": "http", "forward_host": loc_host, "forward_port": 8080, "advanced_config": "" },
                { "path": "/uploads","forward_scheme": "http", "forward_host": loc_host, "forward_port": 8080, "advanced_config": "" }
            ]
        });

        let proxy_host_id: i64;

        // Проверяем, существует ли уже proxy host с таким доменом (без www)
        if let Some(existing_id) = self.find_proxy_host_by_domain(&domain_without_www).await? {
            tracing::info!(
                "Proxy host for {} already exists (id={}), updating instead of creating",
                domain,
                existing_id
            );
            let url = format!("{}/nginx/proxy-hosts/{}", self.base_url, existing_id);
            let resp = self
                .client
                .put(&url)
                .header("Authorization", format!("Bearer {}", token))
                .json(&payload)
                .send()
                .await
                .map_err(|e| format!("NPM Update Host request failed: {}", e))?;

            let status = resp.status();
            if !status.is_success() {
                let err_text = resp.text().await.unwrap_or_default();
                tracing::error!("NPM Update Host response: {} body: {}", status, err_text);
                return Err(format!("NPM Update Host failed: {} - {}", status, err_text));
            }
            tracing::info!(
                "Successfully updated NPM Proxy Host {} for domain {}",
                existing_id,
                domain
            );
            proxy_host_id = existing_id;
        } else {
            // Если не существует — создаём новый
            let url = format!("{}/nginx/proxy-hosts", self.base_url);
            let resp = self
                .client
                .post(&url)
                .header("Authorization", format!("Bearer {}", token))
                .json(&payload)
                .send()
                .await
                .map_err(|e| format!("NPM Create Host request failed: {}", e))?;

            let status = resp.status();
            if !status.is_success() {
                let err_text = resp.text().await.unwrap_or_default();
                tracing::error!("NPM Create Host response: {} body: {}", status, err_text);
                return Err(format!("NPM Create Host failed: {} - {}", status, err_text));
            }

            let data: ProxyHostResponse = resp
                .json()
                .await
                .map_err(|e| format!("NPM Create Host JSON error: {}", e))?;

            tracing::info!(
                "Successfully created NPM Proxy Host {} for domain {}",
                data.id,
                domain
            );
            proxy_host_id = data.id;
        }

        // Теперь запрашиваем SSL-сертификат от Let's Encrypt
        tracing::info!("Requesting SSL certificate for domains: {:?}", domain_names);
        match self.request_ssl_certificate(domain_names).await {
            Ok(certificate_id) => {
                // Привязываем сертификат к Proxy Host
                match self
                    .update_proxy_host_certificate(proxy_host_id, certificate_id)
                    .await
                {
                    Ok(_) => {
                        tracing::info!(
                            "✅ Domain {} fully configured with HTTPS (Proxy Host: {}, Certificate: {})",
                            domain,
                            proxy_host_id,
                            certificate_id
                        );
                    }
                    Err(e) => {
                        tracing::warn!(
                            "⚠️ Certificate obtained but failed to attach to Proxy Host: {}. Manual attachment required in NPM UI.",
                            e
                        );
                        tracing::warn!(
                            "Proxy Host ID: {}, Certificate ID: {}",
                            proxy_host_id,
                            certificate_id
                        );
                    }
                }
            }
            Err(e) => {
                tracing::warn!(
                    "⚠️ Failed to obtain SSL certificate: {}. Proxy Host {} created but requires manual SSL setup in NPM UI.",
                    e,
                    proxy_host_id
                );
                tracing::warn!(
                    "Domain: {}, may be accessible via HTTP only until SSL is configured.",
                    domain
                );
            }
        }

        Ok(proxy_host_id)
    }
}
