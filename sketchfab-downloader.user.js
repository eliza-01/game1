// ==UserScript==
// @name         Sketchfab Downloader — authorized glTF/GLB
// @namespace    local.sketchfab.authorized.downloader
// @version      2.0.0
// @description  Download models you are permitted to access through the official Sketchfab Download API.
// @match        https://sketchfab.com/*
// @match        https://www.sketchfab.com/*
// @run-at       document-idle
// @noframes
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @grant        GM_getValue
// @grant        GM_setValue
// @connect      api.sketchfab.com
// @connect      *
// ==/UserScript==

(() => {
    'use strict';

    const API_BASE = 'https://api.sketchfab.com/v3/models/';
    const TOKEN_KEY = 'authorizedDownloader_apiToken_v2';
    const AUTH_KEY = 'authorizedDownloader_authType_v2';
    const ROOT_ID = 'sf-auth-downloader-v2';

    let activeUid = null;
    let currentUI = null;

    const $ = (root, selector) => root.querySelector(selector);

    function getModelUID() {
        const path = window.location.pathname;
        const from3d = path.match(/(?:^|\/)3d-models\/[^/?#]*?([a-f0-9]{32})(?=\/|$)/i);
        if (from3d) return from3d[1].toLowerCase();
        const fromModels = path.match(/(?:^|\/)models\/([a-f0-9]{32})(?=\/|$)/i);
        return fromModels ? fromModels[1].toLowerCase() : null;
    }

    function fileSafe(str) {
        return String(str || 'sketchfab_model')
            .normalize('NFKC')
            .replace(/[\\/:*?"<>|\x00-\x1f]/g, '_')
            .replace(/\s+/g, '_')
            .replace(/^\.+|\.+$/g, '')
            .slice(0, 90) || 'sketchfab_model';
    }

    function requestJSON(url, authorization = null) {
        return new Promise((resolve, reject) => {
            const headers = { Accept: 'application/json' };
            if (authorization) headers.Authorization = authorization;
            GM_xmlhttpRequest({
                method: 'GET',
                url,
                headers,
                timeout: 30000,
                onload(response) {
                    let data;
                    try { data = JSON.parse(response.responseText); }
                    catch { return reject(new Error(`Сервер вернул не JSON (HTTP ${response.status})`)); }
                    if (response.status < 200 || response.status >= 300) {
                        const details = typeof data?.detail === 'string'
                            ? data.detail : (typeof data?.error === 'string' ? data.error : '');
                        return reject(new Error(`HTTP ${response.status}${details ? ': ' + details : ''}`));
                    }
                    resolve(data);
                },
                onerror: () => reject(new Error('Ошибка сети при обращении к Sketchfab API')),
                ontimeout: () => reject(new Error('Таймаут запроса Sketchfab API'))
            });
        });
    }

    function saveCredential(ui) {
        const token = ui.token.value.trim();
        if (ui.remember.checked && token) {
            GM_setValue(TOKEN_KEY, token);
            GM_setValue(AUTH_KEY, ui.auth.value);
        } else {
            GM_setValue(TOKEN_KEY, '');
        }
    }

    function showStatus(ui, message, isError = false) {
        if (!ui || !ui.root.isConnected) return;
        ui.status.textContent = message;
        ui.status.style.color = isError ? '#ffaaa5' : '#c6cedb';
    }

    function setBusy(ui, busy) {
        ui.busy = busy;
        ui.downloadGltf.disabled = busy;
        ui.downloadGlb.disabled = busy;
    }

    function downloadFile(ui, signedURL, extension) {
        let checked;
        try { checked = new URL(signedURL); }
        catch { throw new Error('API вернул некорректную ссылку на файл'); }
        if (checked.protocol !== 'https:') {
            throw new Error('API вернул небезопасную ссылку (не HTTPS)');
        }

        const name = `${fileSafe(ui.model?.name)}_${ui.uid.slice(0, 8)}.${extension}`;
        showStatus(ui, `Загрузка ${name}...`);
        GM_download({
            url: checked.href,
            name,
            saveAs: false,
            onprogress(e) {
                if (e.lengthComputable && e.total > 0) {
                    showStatus(ui, `Загрузка ${Math.round(e.loaded / e.total * 100)}% — ${name}`);
                }
            },
            onload() {
                showStatus(ui, `Готово: ${name}`);
                setBusy(ui, false);
            },
            onerror(e) {
                showStatus(ui, `Не удалось скачать файл: ${e.error || 'ошибка менеджера загрузок'}`, true);
                setBusy(ui, false);
            },
            ontimeout() {
                showStatus(ui, 'Истекло время скачивания. Попробуйте снова.', true);
                setBusy(ui, false);
            }
        });
    }

    async function handleDownload(ui, format) {
        if (ui.busy) return;
        const token = ui.token.value.trim();
        if (!token) {
            showStatus(ui, 'Укажите API Token в Settings → Password & API или OAuth access token.', true);
            ui.token.focus();
            return;
        }

        saveCredential(ui);
        setBusy(ui, true);
        showStatus(ui, 'Запрашиваю разрешённую ссылку на скачивание...');

        try {
            const authorization = `${ui.auth.value} ${token}`;
            const data = await requestJSON(`${API_BASE}${ui.uid}/download`, authorization);
            if (!ui.root.isConnected) return;

            const entry = data?.[format];
            if (!entry || typeof entry.url !== 'string') {
                const formats = ['gltf', 'glb', 'usdz'].filter(k => data?.[k]?.url);
                throw new Error(`Формат ${format.toUpperCase()} недоступен. Доступно: ${formats.join(', ') || 'нет форматов'}`);
            }

            // glTF from the Download API is a ZIP with scene.gltf, scene.bin and textures/.
            downloadFile(ui, entry.url, format === 'gltf' ? 'zip' : 'glb');
        } catch (error) {
            const msg = String(error?.message || error);
            if (/HTTP 401/.test(msg)) {
                showStatus(ui, '401: неверный/истёкший токен. Проверьте Token или Bearer.', true);
            } else if (/HTTP 403/.test(msg)) {
                showStatus(ui, '403: у аккаунта нет разрешения на скачивание этой модели.', true);
            } else if (/HTTP 404/.test(msg)) {
                showStatus(ui, '404: модель или возможность её скачивания не найдена.', true);
            } else {
                showStatus(ui, msg, true);
            }
            setBusy(ui, false);
        }
    }

    async function fetchModelDetails(ui) {
        try {
            const model = await requestJSON(`${API_BASE}${ui.uid}`);
            if (!ui.root.isConnected || currentUI !== ui) return;
            ui.model = model;
            ui.title.textContent = model.name || 'Без названия';

            const author = model.user?.displayName || model.user?.username || 'Неизвестен';
            const license = model.license?.label || model.license?.slug || 'Не указана';
            ui.details.textContent = `Автор: ${author} · Лицензия: ${license}`;
            if (model.isDownloadable === false) {
                showStatus(ui, 'Публичная загрузка отключена. API проверит ваши права на модель.');
            } else {
                showStatus(ui, 'Модель найдена. Выберите формат и скачайте её.');
            }
        } catch (error) {
            showStatus(ui, `Метаданные недоступны: ${error.message}. Скачивание через токен всё ещё можно попробовать.`, true);
        }
    }

    function createUI(uid) {
        const style = document.createElement('style');
        style.textContent = `
          #${ROOT_ID} { position:fixed; right:20px; bottom:18px; z-index:2147483647;
            font:13px/1.45 system-ui,Segoe UI,Arial,sans-serif; color:#f1f4f8; }
          #${ROOT_ID} * { box-sizing:border-box; }
          #${ROOT_ID} .sf-trigger { border:0; background:#1875ea; color:white; padding:12px 18px;
            border-radius:12px; font-weight:700; cursor:pointer; box-shadow:0 8px 26px #0007; }
          #${ROOT_ID} .sf-panel { display:none; width:min(355px,calc(100vw - 24px)); margin-bottom:12px;
            background:#141924; border:1px solid #3a4659; border-radius:14px;
            padding:16px; box-shadow:0 14px 50px #000b; }
          #${ROOT_ID} .sf-panel.sf-open { display:block; }
          #${ROOT_ID} .sf-heading { font-size:16px; font-weight:750; margin:0 0 8px; }
          #${ROOT_ID} .sf-subtle { color:#aeb8c9; margin:0 0 10px; overflow-wrap:anywhere; }
          #${ROOT_ID} .sf-label { display:block; font-size:12px; color:#c6cedb; margin:10px 0 5px; }
          #${ROOT_ID} input.sf-input, #${ROOT_ID} select.sf-input { width:100%; border:1px solid #506075;
            border-radius:8px; padding:10px; background:#0c111a; color:#fff; font:inherit; }
          #${ROOT_ID} .sf-line { display:flex; gap:8px; align-items:center; margin-top:10px; }
          #${ROOT_ID} .sf-line label { display:flex; gap:6px; align-items:center; cursor:pointer; }
          #${ROOT_ID} .sf-action { flex:1; padding:10px; background:#2679ee; border:0;
            border-radius:8px; color:white; font-weight:700; cursor:pointer; }
          #${ROOT_ID} .sf-action:disabled { cursor:wait; opacity:.5; }
          #${ROOT_ID} .sf-status { margin:12px 0 0; min-height:36px; overflow-wrap:anywhere; }
          #${ROOT_ID} a { color:#99c8ff; }
        `;
        document.head.appendChild(style);

        const root = document.createElement('div');
        root.id = ROOT_ID;
        root.innerHTML = `
            <div class="sf-panel">
                <div class="sf-heading">Sketchfab Downloader</div>
                <div class="sf-subtle sf-title">Загружаю данные модели...</div>
                <div class="sf-subtle sf-details"></div>
                <a class="sf-source" href="${location.href.replace(/"/g, '&quot;')}" target="_blank" rel="noopener noreferrer">Открыть страницу модели</a>
                <label class="sf-label" for="sf-auth-v2">Тип токена</label>
                <select class="sf-input sf-auth" id="sf-auth-v2">
                    <option value="Token">Личный API Token</option>
                    <option value="Bearer">OAuth Bearer token</option>
                </select>
                <label class="sf-label" for="sf-token-v2">Ключ Sketchfab (не пароль аккаунта)</label>
                <input id="sf-token-v2" class="sf-input sf-token" type="password" autocomplete="off" spellcheck="false" placeholder="API Token / OAuth access token">
                <div class="sf-line"><label><input class="sf-remember" type="checkbox"> Сохранить токен локально</label></div>
                <div class="sf-line">
                    <button class="sf-action sf-gltf" type="button">Скачать glTF ZIP</button>
                    <button class="sf-action sf-glb" type="button">GLB</button>
                </div>
                <div class="sf-status" role="status" aria-live="polite">Проверяю модель...</div>
                <div class="sf-subtle" style="margin-top:10px;font-size:11px">Использует официальный Sketchfab API. Только разрешённые модели.</div>
            </div>
            <button type="button" class="sf-trigger">↓ Sketchfab</button>
        `;
        document.body.appendChild(root);

        const ui = {
            uid,
            root,
            style,
            model: null,
            busy: false,
            title: $(root, '.sf-title'),
            details: $(root, '.sf-details'),
            status: $(root, '.sf-status'),
            panel: $(root, '.sf-panel'),
            token: $(root, '.sf-token'),
            auth: $(root, '.sf-auth'),
            remember: $(root, '.sf-remember'),
            downloadGltf: $(root, '.sf-gltf'),
            downloadGlb: $(root, '.sf-glb')
        };
        const stored = GM_getValue(TOKEN_KEY, '');
        ui.token.value = stored;
        ui.remember.checked = Boolean(stored);
        ui.auth.value = GM_getValue(AUTH_KEY, 'Token');
        $(root, '.sf-source').href = location.href;

        $(root, '.sf-trigger').addEventListener('click', () => ui.panel.classList.toggle('sf-open'));
        ui.downloadGltf.addEventListener('click', () => handleDownload(ui, 'gltf'));
        ui.downloadGlb.addEventListener('click', () => handleDownload(ui, 'glb'));
        ui.remember.addEventListener('change', () => {
            if (!ui.remember.checked) GM_setValue(TOKEN_KEY, '');
        });

        return ui;
    }

    function checkPage() {
        const uid = getModelUID();
        if (uid === activeUid && (!uid || currentUI?.root.isConnected)) return;
        activeUid = uid;
        if (currentUI) {
            currentUI.root.remove();
            currentUI.style.remove();
            currentUI = null;
        }
        if (!uid || !document.body || !document.head) return;
        const ui = createUI(uid);
        currentUI = ui;
        fetchModelDetails(ui);
    }

    window.addEventListener('popstate', checkPage);
    window.addEventListener('hashchange', checkPage);
    window.setInterval(checkPage, 1500); // Sketchfab can change URLs without reloading.
    checkPage();
})();
