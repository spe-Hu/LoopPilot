#!/usr/bin/env python3
"""
飞书文档转 Markdown 工具

用法:
  登录(只需一次, 弹出浏览器手动登录):
      python feishu_to_md.py --login

  转换单个文档:
      python feishu_to_md.py <飞书文档URL>
      python feishu_to_md.py <URL> -o 输出.md

  批量转换 Wiki 节点及其所有子页面(保持目录层级):
      python feishu_to_md.py --wiki <Wiki节点URL>
      python feishu_to_md.py --wiki <URL> -o 输出根目录

  调试(查看采集到的块结构):
      python feishu_to_md.py --dump <URL>
"""
import os
import re
import sys
import json
import argparse
import unicodedata

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.path.join(SCRIPT_DIR, ".fb_browser")
DEFAULT_URL = "https://nio.feishu.cn/wiki/EveVwS5kHiN94pkm2IjcCuBXngb"
LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]

# ── 主内容滚动采集 JS ──────────────────────────────────────────────────────────
COLLECT_JS = r"""
(stepRatio) => {
  if (!window.__fbsc) {
    let best = document.scrollingElement, bestH = best ? best.scrollHeight : 0;
    document.querySelectorAll('div').forEach(el => {
      const s = getComputedStyle(el);
      if (/(auto|scroll)/.test(s.overflowY) &&
          el.scrollHeight > el.clientHeight + 100 &&
          el.scrollHeight > bestH) {
        bestH = el.scrollHeight; best = el;
      }
    });
    window.__fbsc = best;
  }
  const sc = window.__fbsc;
  const isTop = (el) => {
    let p = el.parentElement;
    while (p) {
      if (p.getAttribute && p.getAttribute('data-block-id'))
        return p.getAttribute('data-block-type') === 'page';
      p = p.parentElement;
    }
    return false;
  };
  const blocks = [];
  document.querySelectorAll('[data-block-id]').forEach(el => {
    if (!isTop(el)) return;
    const r = el.getBoundingClientRect();
    blocks.push({
      id: el.getAttribute('data-block-id'),
      type: el.getAttribute('data-block-type'),
      y: sc.scrollTop + r.top,
      html: el.outerHTML
    });
  });
  const before = sc.scrollTop;
  sc.scrollTop = before + sc.clientHeight * stepRatio;
  const atBottom = sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 5;
  return { blocks, atBottom, scrollTop: sc.scrollTop, scrollHeight: sc.scrollHeight };
}
"""

# ── 旧版 etherpad 编辑器行采集 JS（滚动由 COLLECT_JS 管理）─────────────────────
ETHERPAD_LINE_JS = r"""
() => {
  const wrap = document.querySelector('.etherpad-container-wrapper');
  if (!wrap) return [];
  const sc = window.__fbsc || { scrollTop: 0 };
  // 收集所有 magicdomid 元素，过滤掉有子 magicdomid 元素的纯容器
  const allEls = [...wrap.querySelectorAll('div[id^="magicdomid"]')];
  const idSet = new Set(allEls.map(e => e.id));
  const lines = [];
  allEls.forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.height === 0) return;
    // 如果元素内部有其他 magicdomid 子元素，它是纯容器，跳过
    const hasChildMagic = el.querySelector('div[id^="magicdomid"]') !== null;
    if (hasChildMagic) return;
    lines.push({ id: el.id, cls: el.className, html: el.innerHTML,
                 y: sc.scrollTop + r.top });
  });
  return lines;
}
"""

# ── Wiki 侧边栏采集 JS ─────────────────────────────────────────────────────────
# 飞书 Wiki 侧边栏树节点没有 href, 只有 class*="tree-view-node-content"
SIDEBAR_NODE_JS = r"""
() => {
  const wrap = document.querySelector('[class*="TreeContentWrapper"]') ||
               document.querySelector('[class*="NavTreeWrapper"]') ||
               document.querySelector('[class*="wiki-space-siderbar"]');
  if (!wrap) return { nodes: [], found: false };
  const nodes = [], seen = new Set();
  wrap.querySelectorAll('[class*="tree-view-node-content"]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.height === 0) return;
    const text = (el.textContent || el.innerText || '').trim().replace(/\s+/g, ' ');
    if (!text) return;
    const key = text + '|' + Math.round(r.left) + '|' + Math.round(r.top);
    if (seen.has(key)) return; seen.add(key);
    nodes.push({ text, x: Math.round(r.left), y: Math.round(r.top) });
  });
  nodes.sort((a, b) => a.y - b.y);
  return { nodes, found: nodes.length > 0 };
}
"""

# 点击指定标题的树节点, 触发导航
SIDEBAR_CLICK_JS = r"""
([text, approxY]) => {
  const wrap = document.querySelector('[class*="TreeContentWrapper"]') ||
               document.querySelector('[class*="NavTreeWrapper"]') ||
               document.querySelector('[class*="wiki-space-siderbar"]');
  if (!wrap) return false;
  const els = [...wrap.querySelectorAll('[class*="tree-view-node-content"]')];
  const target = els.find(el => {
    const r = el.getBoundingClientRect();
    if (r.height === 0) return false;
    const t = (el.textContent || '').trim().replace(/\s+/g, ' ');
    return t === text && Math.abs(r.top - approxY) < 35;
  });
  if (target) { target.click(); return true; }
  return false;
}
"""

SIDEBAR_EXPAND_JS = r"""
() => {
  const wrap = document.querySelector('[class*="TreeContentWrapper"]') ||
               document.querySelector('[class*="NavTreeWrapper"]') ||
               document.querySelector('[class*="wiki-space-siderbar"]');
  if (!wrap) return 0;
  let count = 0;
  wrap.querySelectorAll('[aria-expanded="false"]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) { try { el.click(); count++; } catch(e) {} }
  });
  return count;
}
"""

SIDEBAR_SCROLL_JS = r"""
(delta) => {
  const wrap = document.querySelector('[class*="ScrollableContainer"]') ||
               document.querySelector('[class*="TreeContentWrapper"]') ||
               document.querySelector('[class*="NavTreeWrapper"]');
  if (!wrap) return false;
  if (delta < 0) wrap.scrollTop = 0; else wrap.scrollTop += delta;
  return true;
}
"""

# 返回当前活动（选中）节点的文本和 x 坐标
SIDEBAR_ACTIVE_JS = r"""
() => {
  const active = document.querySelector('[class*="tree-view-node-content--active"]') ||
                 document.querySelector('[class*="tree-view-node-content"][class*="active"]');
  if (!active) return null;
  const r = active.getBoundingClientRect();
  if (r.height === 0) return null;
  const text = (active.textContent || active.innerText || '').trim().replace(/\s+/g, ' ');
  return { text, x: Math.round(r.left), y: Math.round(r.top) };
}
"""


def clean_text(s):
    if not s:
        return ""
    return "".join(c for c in s if unicodedata.category(c) != "Cf").strip()


def _is_login_page(page):
    url = (page.url or "").lower()
    title = (page.title() or "").lower()
    if any(k in url for k in ["login", "passport", "/accounts/"]):
        return True
    if "log in" in title or "登录" in title:
        return True
    return False


# ── 登录 / 调试 ────────────────────────────────────────────────────────────────

def login(url):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            USER_DATA_DIR, headless=False,
            viewport={"width": 1440, "height": 900}, args=LAUNCH_ARGS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print(f"[login] 打开页面: {url}", flush=True)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        print("[login] 如看到登录页, 请在浏览器窗口完成登录(扫码/账号密码)", flush=True)
        print("[login] 等待登录中... (最多 5 分钟)", flush=True)
        import time
        deadline = time.time() + 300
        while time.time() < deadline:
            time.sleep(2)
            try:
                if not _is_login_page(page):
                    time.sleep(5)
                    print(f"[login] 登录成功! {page.url}", flush=True)
                    ctx.close()
                    return True
            except Exception as e:
                print(f"[login] 检测异常(忽略): {e}", flush=True)
        print("[login] 超时未登录", flush=True)
        ctx.close()
        return False


def _collect_blocks(page):
    """边滚动边采集全部顶层块, 按文档顺序返回 [{id,type,y,html}]"""
    page.wait_for_timeout(3000)
    collected = {}
    bottom_streak = 0

    def merge(items):
        for b in items:
            old = collected.get(b["id"])
            if old is None or len(b["html"]) > len(old["html"]):
                collected[b["id"]] = b

    for _ in range(300):
        res = page.evaluate(COLLECT_JS, 0.85)
        merge(res["blocks"])
        page.wait_for_timeout(500)
        if res["atBottom"]:
            bottom_streak += 1
            if bottom_streak >= 2:
                res2 = page.evaluate(COLLECT_JS, 0.0)
                merge(res2["blocks"])
                break
        else:
            bottom_streak = 0
    return sorted(collected.values(), key=lambda b: b["y"])


def _is_etherpad(page):
    """判断当前页面是否为旧版 etherpad 编辑器"""
    return page.evaluate("() => !!document.querySelector('.etherpad-container-wrapper')")


ETHERPAD_INIT_JS = r"""
() => {
  window.__fbsc = null;
  const wrap = document.querySelector('.etherpad-container-wrapper');
  if (!wrap) return { found: false };
  // 先检查 wrap 自身（它本身常常是 overflow:auto 的滚动容器）
  let el = wrap;
  while (el && el !== document.documentElement) {
    const s = getComputedStyle(el);
    if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 50) {
      window.__fbsc = el;
      return { found: true, tag: el.tagName, cls: el.className.substring(0, 80),
               scrollHeight: el.scrollHeight, clientHeight: el.clientHeight };
    }
    el = el.parentElement;
  }
  // fallback: document.scrollingElement
  window.__fbsc = document.scrollingElement;
  const sc = document.scrollingElement;
  return { found: true, tag: 'scrollingElement', cls: '',
           scrollHeight: sc ? sc.scrollHeight : 0, clientHeight: sc ? sc.clientHeight : 0 };
}
"""

def _collect_etherpad_lines(page):
    """滚动采集 etherpad 页面全部行, 返回 [{id,cls,html,y}]"""
    page.wait_for_timeout(5000)
    # 专门为 etherpad 找正确的可滚动容器（不用 COLLECT_JS，防止找到 sidebar）
    info = page.evaluate(ETHERPAD_INIT_JS)
    print(f"[etherpad] 滚动容器: {info}", flush=True)
    page.wait_for_timeout(300)
    # 滚到顶部
    page.evaluate("() => { if (window.__fbsc) window.__fbsc.scrollTop = 0; }")
    page.wait_for_timeout(500)

    collected = {}
    bottom_streak = 0
    # 直接滚动 __fbsc（不经过 COLLECT_JS，避免重置 __fbsc 到错误元素）
    ETHERPAD_SCROLL_JS = r"""
    (stepRatio) => {
      const sc = window.__fbsc;
      if (!sc) return { atBottom: true };
      const before = sc.scrollTop;
      sc.scrollTop = before + sc.clientHeight * stepRatio;
      const atBottom = sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 5;
      return { atBottom, scrollTop: sc.scrollTop, scrollHeight: sc.scrollHeight };
    }
    """

    for _ in range(300):
        # 采集当前可见的 magicdomid 行
        for line in page.evaluate(ETHERPAD_LINE_JS):
            lid = line['id']
            if lid not in collected or len(line['html']) > len(collected[lid]['html']):
                collected[lid] = line
        res = page.evaluate(ETHERPAD_SCROLL_JS, 0.85)
        page.wait_for_timeout(400)
        if res['atBottom']:
            bottom_streak += 1
            if bottom_streak >= 2:
                break
        else:
            bottom_streak = 0

    print(f"[etherpad] 共采集 {len(collected)} 行", flush=True)
    return sorted(collected.values(), key=lambda l: l['y'])


def _etherpad_line_to_md(line, img_map):
    """将单行 etherpad HTML 转为 Markdown 文本"""
    from bs4 import BeautifulSoup
    cls = line.get('cls', '')
    soup = BeautifulSoup(line['html'], 'html.parser')

    # 图片行：先于 fake-text 清理之前提取图片（图片常包在 data-fake-text 内）
    imgs = soup.find_all('img')
    if imgs:
        parts = []
        for img in imgs:
            src = img.get('src', '')
            if not src or src.startswith('blob:') or src.startswith('data:'):
                continue
            local = img_map.get(src, '')
            if local:
                parts.append(f'![image]({local})')
            elif src:
                parts.append(f'![image]({src})')
        return '\n'.join(parts) if parts else ''

    # 无图片行：清理 fake-text 和 pocket 占位元素后提取文本
    for el in soup.select('[data-fake-text], .ace-line-pocket'):
        el.decompose()

    text = clean_text(soup.get_text())
    if not text:
        return ''

    # 列表缩进层级：list-number1=顶级, list-number2=二级...
    def _list_indent(cls, prefix):
        for lvl in range(4, 0, -1):
            if f'{prefix}{lvl}' in cls:
                return lvl - 1   # 0-based indent
        return 0

    if 'heading-h1' in cls:
        return f'## {text}'
    elif 'heading-h2' in cls:
        return f'### {text}'
    elif 'heading-h3' in cls:
        return f'#### {text}'
    elif 'heading-h4' in cls:
        return f'##### {text}'
    elif 'code-block-line' in cls:
        return text   # 调用方负责包 ```
    elif 'list-number' in cls:
        indent = _list_indent(cls, 'list-number')
        return ('  ' * indent) + f'1. {text}'
    elif 'list-bullet' in cls or ('list-div' in cls and 'ol-id' not in cls):
        indent = _list_indent(cls, 'list-bullet')
        return ('  ' * indent) + f'- {text}'
    elif 'ol-id' in cls:
        # 有序列表（ol-id 开头的是编号列表）
        indent = _list_indent(cls, 'list-number')
        return ('  ' * indent) + f'1. {text}'
    else:
        return text


def _download_etherpad_images(page, lines, base_dir, doc_prefix):
    """下载 etherpad 页面的图片, 返回 {src: 本地路径} 映射"""
    img_dir = os.path.join(base_dir, 'images')
    os.makedirs(img_dir, exist_ok=True)
    from bs4 import BeautifulSoup
    img_map = {}
    idx = 1
    cookies = page.context.cookies()
    cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
    headers = {'Cookie': cookie_str, 'Referer': page.url}
    import urllib.request
    for line in lines:
        soup = BeautifulSoup(line['html'], 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src or src in img_map:
                continue
            ext = '.jpg' if '.jpg' in src.lower() else '.png'
            fname = f'{doc_prefix}_img_{idx:02d}{ext}'
            fpath = os.path.join(img_dir, fname)
            try:
                req = urllib.request.Request(src, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    with open(fpath, 'wb') as f:
                        f.write(resp.read())
                img_map[src] = f'images/{fname}'
                print(f'[img] etherpad 已下载 {fname}', flush=True)
                idx += 1
            except Exception as e:
                print(f'[img] 下载失败 {fname}: {e}', flush=True)
    return img_map


def etherpad_to_markdown(lines, title, img_map):
    """将 etherpad 行列表转换为 Markdown 字符串"""
    md_lines = [f'# {title}', '']
    in_code = False
    for line in lines:
        cls = line.get('cls', '')
        # 跳过 IGNORE_HYPERLINK 重复行
        if 'IGNORE_HYPERLINK' in cls:
            continue
        # 跳过 locate 定位锚点行（文档标题/节点锚点，内容已在 # title 中体现）
        # 注意：先检查原始 HTML 有无图片（图片可能在 data-fake-text 内，不能先 decompose）
        if 'locate' in cls and 'heading' not in cls and 'list' not in cls and 'code' not in cls:
            from bs4 import BeautifulSoup
            soup_raw = BeautifulSoup(line['html'], 'html.parser')
            has_img = bool(soup_raw.find_all('img'))
            if not has_img:
                # 无图片：再检查清理后是否有文字内容
                for el in soup_raw.select('.ace-line-pocket, [data-fake-text]'):
                    el.decompose()
                if not clean_text(soup_raw.get_text()):
                    continue  # 纯文本定位锚且无内容，跳过
        # 跳过纯容器 wrapper 行（没有 heading/list 内容且没有图片）
        # 注意：先检查原始 HTML 有无图片，图片可能在 data-fake-text 内
        if 'wrapper' in cls and 'heading' not in cls and 'list' not in cls:
            from bs4 import BeautifulSoup
            soup_w = BeautifulSoup(line['html'], 'html.parser')
            has_img_w = bool(soup_w.find_all('img'))
            if not has_img_w:
                for el in soup_w.select('.ace-line-pocket, [data-fake-text]'):
                    el.decompose()
                if not clean_text(soup_w.get_text()):
                    continue

        converted = _etherpad_line_to_md(line, img_map)
        if converted is None:
            continue

        # 代码块处理：连续的 code-block-line 用 ``` 包裹
        is_code = 'code-block-line' in cls
        if is_code and not in_code:
            md_lines.append('```')
            in_code = True
        elif not is_code and in_code:
            md_lines.append('```')
            md_lines.append('')
            in_code = False

        if is_code:
            md_lines.append(converted.strip('`'))
        elif converted:
            md_lines.append(converted)
        else:
            if md_lines and md_lines[-1] != '':
                md_lines.append('')

    if in_code:
        md_lines.append('```')
    return '\n'.join(md_lines) + '\n'


def _open(p, url, headless=True):
    ctx = p.chromium.launch_persistent_context(
        USER_DATA_DIR, headless=headless,
        viewport={"width": 1440, "height": 900}, args=LAUNCH_ARGS,
        device_scale_factor=2)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=120000)
    return ctx, page


def _crop_whitespace(img_path):
    """裁剪截图底部/右侧的纯白空白区域"""
    try:
        from PIL import Image, ImageChops
        img = Image.open(img_path).convert("RGB")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            margin = 20
            new_w = min(img.width, bbox[2] + margin)
            new_h = min(img.height, bbox[3] + margin)
            img.crop((0, 0, new_w, new_h)).save(img_path)
    except Exception as e:
        print(f"[crop] 裁剪失败 {os.path.basename(img_path)}: {e}", flush=True)


def dump(url):
    if not os.path.exists(USER_DATA_DIR):
        print("[dump] 还没登录, 请先: python feishu_to_md.py --login", flush=True); return
    with sync_playwright() as p:
        ctx, page = _open(p, url)
        if _is_login_page(page):
            print("[dump] 登录态失效, 请重新 --login", flush=True); ctx.close(); return
        blocks = _collect_blocks(page)
        with open(os.path.join(SCRIPT_DIR, "dump_blocks.json"), "w", encoding="utf-8") as f:
            json.dump([{"type": b["type"], "text": clean_text(BeautifulSoup(b["html"], "lxml").get_text(" "))[:80]}
                       for b in blocks], f, ensure_ascii=False, indent=2)
        print(f"[dump] 共采集 {len(blocks)} 个顶层块, 概览已存 dump_blocks.json", flush=True)
        ctx.close()


# ── HTML -> Markdown ───────────────────────────────────────────────────────────

CONTAINER_TYPES = {"callout", "grid", "grid_column", "quote_container"}
IMG_MAP = {}
SCREENSHOT_MAP = {}


def download_images(page, blocks, base_dir, doc_prefix=""):
    mapping = {}
    srcs, seen = [], set()
    for b in blocks:
        soup = BeautifulSoup(b["html"], "lxml")
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src and src.startswith("http") and src not in seen:
                srcs.append(src); seen.add(src)
        for el in soup.find_all(attrs={"style": True}):
            m = re.search(r'url\(["\']?(https?://[^"\')\s]+)', el.get("style", ""))
            if m and m.group(1) not in seen:
                srcs.append(m.group(1)); seen.add(m.group(1))
    if not srcs:
        return mapping
    img_dir = os.path.join(base_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    dp = (doc_prefix + "_") if doc_prefix else ""
    for i, src in enumerate(srcs, 1):
        try:
            resp = page.request.get(src, timeout=60000)
            if not resp.ok:
                print(f"[img] 跳过(HTTP {resp.status}): {src[:60]}", flush=True); continue
            ct = resp.headers.get("content-type", "")
            ext = (".png" if "png" in ct else ".jpg" if "jpeg" in ct or "jpg" in ct
                   else ".gif" if "gif" in ct else ".webp" if "webp" in ct else ".img")
            name = f"{dp}img_{i:02d}{ext}"
            with open(os.path.join(img_dir, name), "wb") as f:
                f.write(resp.body())
            mapping[src] = f"images/{name}"
            print(f"[img] 已下载 {name}", flush=True)
        except Exception as e:
            print(f"[img] 下载失败 {src[:50]}: {e}", flush=True)
    return mapping


def _find_screenshot_targets(blocks):
    NEED_SS = {"whiteboard", "iframe", "base_refer"}
    targets, seen = [], set()
    for b in blocks:
        soup = BeautifulSoup(b["html"], "lxml")
        for el in soup.find_all(attrs={"data-block-id": True}):
            bid = el.get("data-block-id")
            if bid in seen: continue
            btype = el.get("data-block-type", "")
            if btype in NEED_SS:
                seen.add(bid); targets.append((bid, btype, b["y"], b["id"]))
            elif btype == "image":
                src = _img_src(el)
                if not src or src.startswith("blob:"):
                    seen.add(bid); targets.append((bid, "image_blob", b["y"], b["id"]))
    return targets


def screenshot_blocks(page, blocks, base_dir, doc_prefix=""):
    targets = _find_screenshot_targets(blocks)
    if not targets:
        return {}
    img_dir = os.path.join(base_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    page.evaluate(COLLECT_JS, 0.0)
    mapping, parent_ss, ss_idx = {}, {}, [0]
    dp = (doc_prefix + "_") if doc_prefix else ""

    def _do_screenshot(locator, base_name):
        ss_idx[0] += 1
        name = f"{dp}{base_name}_{ss_idx[0]:02d}.png"
        full_path = os.path.join(img_dir, name)
        locator.screenshot(path=full_path)
        _crop_whitespace(full_path)
        return f"images/{name}"

    def _scroll_to(y):
        page.evaluate("(y) => { const sc = window.__fbsc || document.scrollingElement; if (sc) sc.scrollTop = Math.max(0, y-200); }", y)

    for bid, btype, approx_y, parent_id in targets:
        _scroll_to(approx_y)
        page.wait_for_timeout(3000 if btype == "whiteboard" else 1500)
        locator = page.locator(f'[data-block-id="{bid}"]')
        try:
            locator.wait_for(state="visible", timeout=6000)
            rel = _do_screenshot(locator, "img_ss")
            mapping[bid] = rel
            print(f"[screenshot] 已截图 {btype}: {rel}", flush=True)
        except Exception:
            if parent_id in parent_ss:
                mapping[bid] = parent_ss[parent_id]
                print(f"[screenshot] 复用父块截图: {parent_ss[parent_id]}", flush=True)
            else:
                _scroll_to(approx_y)
                page.wait_for_timeout(2000)
                p_loc = page.locator(f'[data-block-id="{parent_id}"]')
                try:
                    p_loc.wait_for(state="visible", timeout=6000)
                    rel = _do_screenshot(p_loc, "img_ss")
                    parent_ss[parent_id] = rel; mapping[bid] = rel
                    print(f"[screenshot] fallback 截父块 {btype}: {rel}", flush=True)
                except Exception as e2:
                    print(f"[screenshot] 截图彻底失败 {btype}/{bid[:8]}: {e2}", flush=True)
    return mapping


def _children_blocks(el):
    out = []
    for c in el.select("[data-block-id]"):
        p = c.parent
        while p is not None:
            if p.has_attr("data-block-id"):
                if p is el: out.append(c)
                break
            p = p.parent
    return out


def _inline_text(el):
    return clean_text(el.get_text(" "))


def _img_src(el):
    img = el.find("img")
    if img and img.get("src"): return img.get("src")
    for d in el.find_all(attrs={"style": True}):
        m = re.search(r'url\(["\']?(.*?)["\']?\)', d.get("style", ""))
        if m: return m.group(1)
    return None


def block_to_md(el, btype):
    if btype == "callout":
        inner = _render_children(el)
        return "\n".join("> " + ln if ln else ">" for ln in inner.split("\n"))
    if btype in ("grid", "grid_column"):
        return _render_children(el)
    if btype in ("quote_container", "quote"):
        inner = _render_children(el) or _inline_text(el)
        return "\n".join("> " + ln if ln else ">" for ln in inner.split("\n"))
    if btype and btype.startswith("heading"):
        m = re.search(r"\d+", btype)
        level = int(m.group()) if m else 1
        return "#" * max(1, min(level, 6)) + " " + _inline_text(el)
    if btype == "ordered":
        t = _inline_text(el)
        return t if re.match(r"^\d+[.)]", t) else "1. " + t
    if btype in ("bullet", "todo"):
        return "- " + re.sub(r"^[•·▪◦‣·\-]\s*", "", _inline_text(el))
    if btype == "image":
        bid = el.get("data-block-id", "") if hasattr(el, "get") else ""
        ss = SCREENSHOT_MAP.get(bid)
        if ss: return f"![image]({ss})"
        src = _img_src(el)
        if not src: return "![image](图片未能识别)"
        local = IMG_MAP.get(src)
        return f"![image]({local})" if local else f"![image]({src})"
    if btype == "divider": return "---"
    if btype == "code": return "```\n" + _inline_text(el) + "\n```"
    if btype == "whiteboard":
        bid = el.get("data-block-id", "") if hasattr(el, "get") else ""
        ss = SCREENSHOT_MAP.get(bid)
        return f"![画板内容]({ss})\n\n*[此处为画板/思维导图]*" if ss else "> [画板/思维导图: 此处为图形内容, 无法转为文本]"
    if btype == "iframe":
        bid = el.get("data-block-id", "") if hasattr(el, "get") else ""
        ss = SCREENSHOT_MAP.get(bid)
        return f"![嵌入内容]({ss})\n\n*[此处为嵌入电子表格/文档]*" if ss else "> [嵌入内容(iframe), 无法转为文本]"
    if btype == "base_refer":
        bid = el.get("data-block-id", "") if hasattr(el, "get") else ""
        ss = SCREENSHOT_MAP.get(bid)
        return f"![多维表格]({ss})\n\n*[此处为多维表格引用]*" if ss else "> [多维表格引用, 无法转为文本]"
    if btype == "table": return _table_to_md(el)
    return _inline_text(el)


def _render_children(el):
    parts = []
    for c in _children_blocks(el):
        md = block_to_md(c, c.get("data-block-type"))
        if md.strip(): parts.append(md)
    return "\n\n".join(parts)


def _table_to_md(el):
    rows = el.select('[class*="table-row"], tr')
    out = []
    for r in rows:
        cells = r.select('[class*="table-cell"], td, th')
        out.append("| " + " | ".join(_inline_text(c) for c in cells) + " |")
    if len(out) >= 1:
        cols = out[0].count("|") - 1
        out.insert(1, "| " + " | ".join(["---"] * cols) + " |")
    return "\n".join(out)


def blocks_to_markdown(blocks, title):
    lines = []
    if title:
        lines.append("# " + title)
        lines.append("")
    for b in blocks:
        btype = b["type"]
        if btype == "page": continue
        soup = BeautifulSoup(b["html"], "lxml")
        el = soup.find(attrs={"data-block-id": b["id"]}) or soup
        md = block_to_md(el, btype)
        if md is not None and md.strip() != "":
            lines.append(md)
            lines.append("")
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def screenshot_full_document(page, output_path):
    """滚动截图整个文档并拼接成完整长图"""
    from PIL import Image, ImageChops
    import io
    DPR = 2

    page.evaluate(COLLECT_JS, 0.0)
    page.evaluate("() => { const sc = window.__fbsc || document.scrollingElement; if (sc) sc.scrollTop = 0; }")
    page.wait_for_timeout(2000)

    info = page.evaluate("""() => {
        const sc = window.__fbsc || document.scrollingElement;
        const inner = sc && sc !== document.scrollingElement && sc !== document.body;
        const r = inner ? sc.getBoundingClientRect() : {left:0, top:0, width:window.innerWidth};
        const ch = inner ? sc.clientHeight : window.innerHeight;
        return { scrollHeight: sc ? sc.scrollHeight : document.body.scrollHeight,
                 clientHeight: ch, x: r.left, y: r.top, width: r.width };
    }""")
    sh, ch = info['scrollHeight'], info['clientHeight']
    if not sh or not ch or not info['width']:
        print("[backup] 文档为空, 跳过截图", flush=True)
        return
    clip = {"x": info['x'], "y": info['y'], "width": info['width'], "height": ch}
    step = int(ch * 0.85)

    frames, pos, last = [], 0, -1
    while True:
        page.evaluate(f"() => {{ const sc = window.__fbsc || document.scrollingElement; if (sc) sc.scrollTop = {pos}; }}")
        page.wait_for_timeout(1500)
        try:
            page.wait_for_function("() => [...document.querySelectorAll('img')].every(i=>i.complete)", timeout=3000)
        except Exception:
            pass
        actual = page.evaluate("() => { const sc = window.__fbsc || document.scrollingElement; return sc ? sc.scrollTop : 0; }")
        if actual == last: break
        last = actual
        frames.append((actual, Image.open(io.BytesIO(page.screenshot(clip=clip)))))
        print(f"[backup] 截图进度 {actual}/{sh} px", flush=True)
        if actual + ch >= sh - 5: break
        pos = actual + step

    if not frames: return
    total_h = int(sh * DPR) + frames[-1][1].height
    result = Image.new('RGB', (frames[0][1].width, total_h), (255, 255, 255))
    for scroll_top, img in frames:
        result.paste(img, (0, int(scroll_top * DPR)))
    bg = Image.new("RGB", result.size, (255, 255, 255))
    diff = ImageChops.difference(result, bg)
    bbox = diff.getbbox()
    if bbox:
        result = result.crop((0, 0, result.width, min(result.height, bbox[3] + 40)))
    result.save(output_path)
    kb = os.path.getsize(output_path) // 1024
    print(f"[backup] 全文截图: {os.path.basename(output_path)} ({result.width}×{result.height}px, {kb}KB)", flush=True)


# ── Wiki 批量转换 ──────────────────────────────────────────────────────────────

def _collect_wiki_tree(page, start_url):
    """只采集 start_url 节点及其子树, 按树序返回 [{url,title,x}]"""
    page.wait_for_timeout(3000)
    all_nodes = {}    # url -> {url,title,x}  insertion order = tree order
    visited_texts = set()

    def _get_nodes():
        res = page.evaluate(SIDEBAR_NODE_JS)
        return res.get('nodes', []), res.get('found', False)

    # 获取起始节点的 x 坐标（深度）和标题
    root_info = None
    for _ in range(8):
        root_info = page.evaluate(SIDEBAR_ACTIVE_JS)
        if root_info:
            break
        page.wait_for_timeout(1000)

    if not root_info:
        print("[wiki] 未找到活动节点，采集整个侧边栏", flush=True)
        root_x = -1   # -1 表示不限深度（全量采集）
        root_text = None
    else:
        root_x = root_info['x']
        root_text = root_info['text']
        print(f"[wiki] 起始节点: '{root_text}'  (缩进 x={root_x})", flush=True)
        start_clean = start_url.split('?')[0].rstrip('/')
        all_nodes[start_clean] = {'url': start_clean, 'title': root_text, 'x': root_x}
        visited_texts.add(root_text)
        print(f"[wiki] 发现(1): {root_text}", flush=True)

    # 滚回顶部开始扫描
    page.evaluate(SIDEBAR_SCROLL_JS, -1)
    page.wait_for_timeout(500)

    # past_root: 是否已经在侧边栏列表中扫过了 root 节点
    past_root = (root_text is None)   # 全量模式直接为 True
    subtree_done = False
    # scroll_empty 仅在 past_root=True 时计数（"已过 root 后连续空滚次数"）
    scroll_empty = 0
    # find_root_scroll: 在 past_root=False 时计数, 防止无限滚找 root
    find_root_scroll = 0

    for _ in range(2000):
        if len(all_nodes) >= 500 or subtree_done:
            break

        nodes, _ = _get_nodes()

        # 扫描当前可见节点, 找第一个合法目标
        target = None
        for n in nodes:
            if not past_root:
                if n['text'] == root_text and n['x'] == root_x:
                    past_root = True   # 找到 root, 后面的才是子节点
                continue  # root 之前的节点全部跳过

            # ---- 已经过了 root ----
            if root_text is not None and n['x'] <= root_x:
                # 遇到同级/父级节点 → 子树结束
                subtree_done = True
                break

            if n['text'] not in visited_texts:
                target = n
                break

        if subtree_done:
            break

        if target is None:
            # 当前视口无目标 → 向下滚动
            page.evaluate(SIDEBAR_SCROLL_JS, 250)
            page.wait_for_timeout(300)
            if past_root:
                scroll_empty += 1
                if scroll_empty >= 20:   # 子树扫完
                    break
            else:
                find_root_scroll += 1
                if find_root_scroll >= 60:   # 找不到 root, 放弃
                    print("[wiki] 未在侧边栏找到起始节点", flush=True)
                    break
            continue

        scroll_empty = 0
        text = target['text']
        visited_texts.add(text)

        clicked = page.evaluate(SIDEBAR_CLICK_JS, [text, target['y']])
        if clicked:
            page.wait_for_timeout(800)
            url = page.url.split('?')[0].rstrip('/')
            if url not in all_nodes:
                all_nodes[url] = {'url': url, 'title': text, 'x': target['x']}
                print(f"[wiki] 发现({len(all_nodes)}): {text}", flush=True)

        # 导航后滚回顶, 重新从 root 位置开始扫描子节点
        page.evaluate(SIDEBAR_SCROLL_JS, -1)
        past_root = False   # 重置: 需要在列表中重新定位 root
        find_root_scroll = 0
        page.wait_for_timeout(400)

    page.evaluate(SIDEBAR_SCROLL_JS, -1)
    page.wait_for_timeout(500)
    return list(all_nodes.values())


def _build_dir_tree(nodes, start_url):
    """根据节点的 x 坐标推断层级, 构建 {url: (输出相对目录, 标题)} 映射"""
    if not nodes:
        return {}

    start_url = start_url.split('?')[0].rstrip('/')

    # 找起始节点
    start_idx = None
    for i, n in enumerate(nodes):
        if n['url'].rstrip('/') == start_url:
            start_idx = i
            break

    if start_idx is None:
        print(f"[wiki] 起始URL未在侧边栏找到, 将转换全部 {len(nodes)} 个节点", flush=True)
        subtree = nodes
    else:
        start_x = nodes[start_idx]['x']
        subtree = [nodes[start_idx]]
        for n in nodes[start_idx + 1:]:
            if n['x'] < start_x:  # 遇到父级/同级节点, 停止
                break
            subtree.append(n)

    if not subtree:
        return {}

    # x → 深度(0-based): x 越大层级越深
    x_vals = sorted(set(n['x'] for n in subtree))
    x_to_depth = {x: i for i, x in enumerate(x_vals)}

    # 用栈构建相对目录路径
    stack = []  # [(depth, safe_dirname)]
    result = {}
    for n in subtree:
        depth = x_to_depth[n['x']]
        safe = re.sub(r'[\\/:*?"<>|]', '_', n['title']).strip('_ ') or 'untitled'
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, safe))
        rel_dir = os.path.join(*[s[1] for s in stack])
        result[n['url'].rstrip('/')] = (rel_dir, n['title'])

    return result


def _convert_page(page, url, output):
    """在已打开的浏览器中转换单个飞书文档, 返回是否成功"""
    global IMG_MAP, SCREENSHOT_MAP

    page.goto(url, wait_until="domcontentloaded", timeout=120000)
    if _is_login_page(page):
        print(f"[convert] 登录态失效", flush=True)
        return False

    # 等待页面内容加载（wiki 页面标题由 JS 异步设置）
    page.wait_for_timeout(3000)
    raw_title = clean_text(page.title()).replace(" - 飞书云文档", "").strip()

    # 如果标题是 wiki 空间名或过于通用，尝试从侧边栏活动节点获取实际文档标题
    GENERIC_TITLES = {"wiki", "docs", "飞书云文档", "feishu", ""}
    if raw_title.lower() in GENERIC_TITLES:
        for _ in range(5):
            info = page.evaluate(SIDEBAR_ACTIVE_JS)
            if info and info.get('text') and info['text'].lower() not in GENERIC_TITLES:
                raw_title = info['text']
                break
            page.wait_for_timeout(1000)

    if not raw_title or raw_title.lower() in GENERIC_TITLES:
        raw_title = "feishu_doc"
    print(f"[convert] 文档标题: {raw_title}", flush=True)

    safe = re.sub(r"[\\/:*?\"<>|]", "_", raw_title) or "feishu_doc"
    if output:
        base_dir = os.path.dirname(os.path.abspath(output))
        doc_prefix = os.path.splitext(os.path.basename(output))[0]
    else:
        base_dir = os.path.join(SCRIPT_DIR, safe)
        os.makedirs(base_dir, exist_ok=True)
        output = os.path.join(base_dir, safe + ".md")
        doc_prefix = safe

    os.makedirs(base_dir, exist_ok=True)

    # 检测页面类型: 旧版 etherpad 还是新版 block 编辑器
    page.wait_for_timeout(2000)
    if _is_etherpad(page):
        print("[convert] 检测到旧版 etherpad 编辑器, 使用 etherpad 采集路径", flush=True)
        lines = _collect_etherpad_lines(page)
        print(f"[convert] 采集到 {len(lines)} 行", flush=True)
        img_map = _download_etherpad_images(page, lines, base_dir, doc_prefix)
        md = etherpad_to_markdown(lines, raw_title, img_map)
        print("[convert] 正在生成全文备份截图...", flush=True)
        screenshot_full_document(page, os.path.join(base_dir, doc_prefix + "_backup.png"))
    else:
        print("[convert] 正在滚动采集全文块...", flush=True)
        blocks = _collect_blocks(page)
        print(f"[convert] 采集到 {len(blocks)} 个顶层块", flush=True)

        print("[convert] 正在下载图片...", flush=True)
        IMG_MAP = download_images(page, blocks, base_dir, doc_prefix)
        print(f"[convert] 图片下载完成, 共 {len(IMG_MAP)} 张", flush=True)

        print("[convert] 正在截图动态内容(blob图片/画板/嵌入块)...", flush=True)
        SCREENSHOT_MAP = screenshot_blocks(page, blocks, base_dir, doc_prefix)
        print(f"[convert] 截图完成, 共 {len(SCREENSHOT_MAP)} 个", flush=True)

        print("[convert] 正在生成全文备份截图...", flush=True)
        screenshot_full_document(page, os.path.join(base_dir, doc_prefix + "_backup.png"))

        md = blocks_to_markdown(blocks, raw_title)

    with open(output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[convert] 已保存: {output}  ({len(md)} 字符)", flush=True)
    return True


def convert(url, output):
    if not os.path.exists(USER_DATA_DIR):
        print("[convert] 还没登录, 请先: python feishu_to_md.py --login", flush=True); return
    with sync_playwright() as p:
        ctx, page = _open(p, url)
        if _is_login_page(page):
            print("[convert] 登录态失效, 请重新 --login", flush=True); ctx.close(); return
        _convert_page(page, url, output)
        ctx.close()


def convert_wiki(start_url, output_base=None):
    """将飞书 Wiki 节点及其所有子页面批量转换为 Markdown, 保持目录层级"""
    if not os.path.exists(USER_DATA_DIR):
        print("[wiki] 还没登录, 请先: python feishu_to_md.py --login", flush=True); return
    if output_base is None:
        output_base = SCRIPT_DIR

    with sync_playwright() as p:
        ctx, page = _open(p, start_url)
        if _is_login_page(page):
            print("[wiki] 登录态失效, 请重新 --login", flush=True); ctx.close(); return

        print("[wiki] 正在采集 Wiki 树结构...", flush=True)
        nodes = _collect_wiki_tree(page, start_url)

        if not nodes:
            print("[wiki] 未采集到节点, 回退为单页转换", flush=True)
            _convert_page(page, start_url, None)
            ctx.close(); return

        dir_map = _build_dir_tree(nodes, start_url)
        total = len(dir_map)
        print(f"\n[wiki] 共发现 {total} 个页面, 开始逐一转换...\n", flush=True)

        ok, fail = 0, 0
        for idx, (url, (rel_dir, title)) in enumerate(dir_map.items(), 1):
            print(f"━━ [{idx}/{total}] {title}", flush=True)
            out_dir = os.path.join(output_base, rel_dir)
            os.makedirs(out_dir, exist_ok=True)
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title).strip('_ ') or 'untitled'
            output = os.path.join(out_dir, safe_title + ".md")
            try:
                if _convert_page(page, url, output):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"[wiki] 转换失败: {e}", flush=True)
                fail += 1

        ctx.close()
    print(f"\n[wiki] 全部完成: ✓ {ok} 成功  ✗ {fail} 失败", flush=True)


def main():
    parser = argparse.ArgumentParser(description="飞书文档转 Markdown")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--dump", action="store_true")
    parser.add_argument("--wiki", action="store_true",
                        help="批量转换 Wiki 节点及所有子页面(保持目录层级)")
    parser.add_argument("-o", "--output", default=None,
                        help="单页: 输出.md 路径; --wiki: 输出根目录")
    args = parser.parse_args()
    if args.login:
        login(args.url)
    elif args.dump:
        dump(args.url)
    elif args.wiki:
        convert_wiki(args.url, args.output)
    else:
        convert(args.url, args.output)


if __name__ == "__main__":
    main()
