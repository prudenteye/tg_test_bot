'use strict';

const path = require('path');
const fs = require('fs/promises');
const http = require('http');
const express = require('express');
const extractZip = require('extract-zip');
const { nanoid } = require('nanoid');
require('dotenv').config();

const app = express();
app.use(express.json({ limit: '50mb' }));

// Config
const BOT_TOKEN = process.env.BOT_TOKEN;
const PUBLIC_BASE_URL = process.env.PUBLIC_BASE_URL; // e.g., https://your-domain.com
const PORT = process.env.PORT || 3000;
const DEPLOY_ROOT = path.join(process.cwd(), 'deployments');

if (!BOT_TOKEN || !PUBLIC_BASE_URL) {
  console.error('Missing BOT_TOKEN or PUBLIC_BASE_URL. Please set environment variables or .env file.');
  process.exit(1);
}

// Serve deployed apps at /apps/:id/...
app.use('/apps', express.static(DEPLOY_ROOT, { extensions: ['html', 'htm'] }));

app.get('/health', (_req, res) => {
  res.json({ ok: true, ts: Date.now() });
});

// Webhook route bound to token to reduce abuse
const webhookPath = `/webhook/${BOT_TOKEN}`;
app.post(webhookPath, async (req, res) => {
  // Quickly ACK to Telegram
  res.status(200).json({ ok: true });

  try {
    const update = req.body;
    const message = update && (update.message || update.edited_message);
    if (!message) return;

    const chatId = message.chat && message.chat.id;
    const hasDoc = message.document;
    const text = message.text;

    if (text && /^\/start\b/.test(text)) {
      await sendMessage(chatId, [
        '你好，我可以接收你的代码包并部署为静态站点。',
        '请发送 zip（根目录包含 index.html），或直接发送一个 HTML 文件。',
        '部署完成后，我会返回访问链接。'
      ].join('\n'));
      return;
    }

    if (!hasDoc) {
      await sendMessage(chatId, '请发送 zip 包（包含 index.html）或单个 HTML 文件。');
      return;
    }

    // Handle document
    const doc = message.document;
    const fileId = doc.file_id;
    const fileName = doc.file_name || 'upload';
    const mime = doc.mime_type || '';

    const { buffer, remotePath } = await downloadTelegramFile(fileId);
    // Decide deployment strategy
    const lowerName = fileName.toLowerCase();
    const isZip = lowerName.endsWith('.zip') || mime.includes('zip');
    const isHtml = lowerName.endsWith('.html') || lowerName.endsWith('.htm') || mime.includes('text/html');

    if (!isZip && !isHtml) {
      await sendMessage(chatId, '仅支持 zip（包含 index.html）或单个 HTML 文件。请检查文件类型后重试。');
      return;
    }

    const deployId = nanoid(10);
    const targetDir = path.join(DEPLOY_ROOT, deployId);
    await fs.mkdir(targetDir, { recursive: true });

    let url = `${PUBLIC_BASE_URL.replace(/\/+$/, '')}/apps/${deployId}/`;

    if (isZip) {
      const zipPath = path.join(targetDir, 'source.zip');
      await fs.writeFile(zipPath, buffer);
      try {
        await extractZip(zipPath, { dir: targetDir });
      } catch (e) {
        await sendMessage(chatId, '解压失败，请确认上传的是有效的 zip 包。');
        return;
      }
      // Quick check for index.html presence (top-level)
      const indexTop = path.join(targetDir, 'index.html');
      const indexTopAlt = path.join(targetDir, 'index.htm');
      const hasTopIndex = await exists(indexTop) || await exists(indexTopAlt);

      if (!hasTopIndex) {
        // Try common case: a single top-level folder inside the zip
        const entries = await fs.readdir(targetDir, { withFileTypes: true });
        const dirs = entries.filter(e => e.isDirectory()).map(e => e.name);
        if (dirs.length === 1) {
          // Adjust URL so that /apps/:id/ maps to that folder seamlessly (express serves directory)
          // No extra changes needed; but we can optionally move files up.
          const nestedIndex = path.join(targetDir, dirs[0], 'index.html');
          const nestedIndexAlt = path.join(targetDir, dirs[0], 'index.htm');
          const hasNestedIndex = await exists(nestedIndex) || await exists(nestedIndexAlt);
          if (!hasNestedIndex) {
            await sendMessage(chatId, 'zip 解压后未找到 index.html，请确保根目录或唯一子目录下存在 index.html。');
            return;
          }
          // Keep structure; static middleware will serve /apps/:id/dirs[0]/index.html
          url = `${PUBLIC_BASE_URL.replace(/\/+$/, '')}/apps/${deployId}/${dirs[0]}/`;
        } else {
          // Multiple items and no top-level index.html
          await sendMessage(chatId, '未在 zip 根目录找到 index.html，请将 index.html 放在根目录或唯一子目录中。');
          return;
        }
      }
    } else if (isHtml) {
      // Single HTML file -> write as index.html
      await fs.writeFile(path.join(targetDir, 'index.html'), buffer);
    }

    await sendMessage(chatId, `部署成功：\n${url}`);
  } catch (err) {
    console.error('Error handling update:', err);
    // Try not to crash; optionally notify user if chatId known (omitted here)
  }
});

async function sendMessage(chatId, text) {
  if (!chatId) return;
  const endpoint = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text })
  });
  if (!resp.ok) {
    const t = await resp.text().catch(() => '');
    console.warn('sendMessage failed:', resp.status, t);
  }
}

async function downloadTelegramFile(fileId) {
  const getFileUrl = `https://api.telegram.org/bot${BOT_TOKEN}/getFile?file_id=${encodeURIComponent(fileId)}`;
  const r = await fetch(getFileUrl);
  if (!r.ok) {
    throw new Error(`getFile failed: ${r.status}`);
  }
  const data = await r.json();
  if (!data.ok || !data.result || !data.result.file_path) {
    throw new Error('Invalid getFile response');
  }
  const filePath = data.result.file_path;
  const fileUrl = `https://api.telegram.org/file/bot${BOT_TOKEN}/${filePath}`;
  const dl = await fetch(fileUrl);
  if (!dl.ok) {
    throw new Error(`download failed: ${dl.status}`);
  }
  const buffer = Buffer.from(await dl.arrayBuffer());
  return { buffer, remotePath: filePath };
}

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

// Ensure deployments directory exists
(async () => {
  await fs.mkdir(DEPLOY_ROOT, { recursive: true });
})();

const server = http.createServer(app);
server.listen(PORT, () => {
  console.log(`Server listening on :${PORT}`);
  console.log(`Webhook path: ${webhookPath}`);
  console.log(`Set your Telegram webhook to: ${PUBLIC_BASE_URL.replace(/\/+$/, '')}${webhookPath}`);
});