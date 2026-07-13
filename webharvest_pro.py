import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import random
import os
from datetime import datetime
import webbrowser

# ── Palette ──────────────────────────────────────────────────────────────────
BG_DARK    = "#0D1117"
BG_CARD    = "#161B22"
BG_INPUT   = "#21262D"
ACCENT     = "#58A6FF"
ACCENT2    = "#3FB950"
ACCENT3    = "#F78166"
TEXT_PRI   = "#E6EDF3"
TEXT_SEC   = "#8B949E"
BORDER     = "#30363D"
HOVER      = "#1F6FEB"
WARN       = "#D29922"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SITE_CONFIGS = {
    "Books to Scrape (books.toscrape.com)": {
        "url":        "https://books.toscrape.com/catalogue/",
        "base_url":   "https://books.toscrape.com/catalogue/",
        "home":       "https://books.toscrape.com/",
        "item_sel":   "article.product_pod",
        "name_sel":   "h3 a",
        "price_sel":  "p.price_color",
        "rating_sel": "p.star-rating",
        "img_sel":    "img",
        "next_sel":   "li.next a",
        "rating_map": {"One":"1★","Two":"2★","Three":"3★","Four":"4★","Five":"5★"},
        "pages":      50,
        "category":   "Books",
    },
    "Quotes to Scrape (quotes.toscrape.com)": {
        "url":        "https://quotes.toscrape.com/",
        "base_url":   "https://quotes.toscrape.com",
        "home":       "https://quotes.toscrape.com/",
        "item_sel":   "div.quote",
        "name_sel":   "small.author",
        "price_sel":  None,
        "rating_sel": None,
        "img_sel":    None,
        "next_sel":   "li.next a",
        "rating_map": {},
        "pages":      10,
        "category":   "Quotes",
    },
}

RATING_WORDS = {"one":"1★","two":"2★","three":"3★","four":"4★","five":"5★"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_books(soup, cfg):
    items, articles = [], soup.select(cfg["item_sel"])
    for a in articles:
        name  = a.select_one(cfg["name_sel"])
        name  = name["title"] if name and name.has_attr("title") else (name.get_text(strip=True) if name else "N/A")
        price_el = a.select_one(cfg["price_sel"]) if cfg["price_sel"] else None
        price = price_el.get_text(strip=True) if price_el else "N/A"
        rat_el = a.select_one(cfg["rating_sel"]) if cfg["rating_sel"] else None
        if rat_el:
            cls = [c for c in rat_el.get("class",[]) if c.lower() in cfg["rating_map"] or c.lower() in RATING_WORDS]
            rating = cfg["rating_map"].get(cls[0], RATING_WORDS.get(cls[0].lower(),"N/A")) if cls else "N/A"
        else:
            rating = "N/A"
        img_el = a.select_one(cfg["img_sel"]) if cfg["img_sel"] else None
        img    = img_el["src"] if img_el and img_el.has_attr("src") else "N/A"
        items.append({"Name": name, "Price": price, "Rating": rating,
                      "Image URL": img, "Category": cfg["category"],
                      "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M")})
    return items

def parse_quotes(soup, cfg):
    items = []
    for q in soup.select(cfg["item_sel"]):
        text   = q.select_one("span.text")
        author = q.select_one("small.author")
        tags   = [t.get_text(strip=True) for t in q.select("a.tag")]
        items.append({
            "Name":     author.get_text(strip=True) if author else "N/A",
            "Price":    "N/A",
            "Rating":   "N/A",
            "Quote":    text.get_text(strip=True) if text else "N/A",
            "Tags":     ", ".join(tags),
            "Category": cfg["category"],
            "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
    return items

PARSERS = {
    "Books to Scrape (books.toscrape.com)": parse_books,
    "Quotes to Scrape (quotes.toscrape.com)": parse_quotes,
}

# ── Main App ──────────────────────────────────────────────────────────────────

class ScraperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WebHarvest Pro — E-Commerce Scraper")
        self.geometry("1160x780")
        self.minsize(900, 640)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        self._products    = []
        self._stop_flag   = False
        self._thread      = None
        self._anim_step   = 0
        self._anim_id     = None

        self._build_ui()
        self._tick_clock()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=18, pady=(6,14))
        main.columnconfigure(0, weight=0, minsize=310)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        self._build_sidebar(main)
        self._build_right(main)

    def _build_topbar(self):
        bar = tk.Frame(self, bg=BG_CARD, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        lbl = tk.Label(bar, text="⬡  WebHarvest Pro", font=("Helvetica",16,"bold"),
                       bg=BG_CARD, fg=ACCENT)
        lbl.pack(side="left", padx=20, pady=14)

        self._clock_lbl = tk.Label(bar, text="", font=("Helvetica",10),
                                   bg=BG_CARD, fg=TEXT_SEC)
        self._clock_lbl.pack(side="right", padx=20)

        tag = tk.Label(bar, text="v2.0  •  Ethical Scraper", font=("Helvetica",9),
                       bg=BG_CARD, fg=TEXT_SEC)
        tag.pack(side="right", padx=4)

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG_CARD, width=310)
        sb.grid(row=0, column=0, sticky="nsew", padx=(0,14), pady=4)
        sb.grid_propagate(False)

        # Section: Target
        self._section(sb, "🎯  TARGET WEBSITE")
        self._site_var = tk.StringVar(value=list(SITE_CONFIGS.keys())[0])
        opt = ttk.OptionMenu(sb, self._site_var, self._site_var.get(), *SITE_CONFIGS.keys(),
                             command=self._on_site_change)
        opt.configure(style="Dark.TMenubutton")
        opt.pack(fill="x", padx=14, pady=(0,10))

        self._section(sb, "⚙️  SCRAPE SETTINGS")
        self._pages_var = tk.IntVar(value=3)
        self._slider_row(sb, "Pages to scrape", self._pages_var, 1, 10)

        self._delay_var = tk.DoubleVar(value=0.5)
        self._slider_row(sb, "Delay (sec)", self._delay_var, 0.1, 3.0, resolution=0.1)

        # Output format
        self._section(sb, "💾  OUTPUT FORMAT")
        self._fmt_var = tk.StringVar(value="CSV")
        frow = tk.Frame(sb, bg=BG_CARD)
        frow.pack(fill="x", padx=14, pady=(0,10))
        for fmt in ("CSV","JSON","Both"):
            tk.Radiobutton(frow, text=fmt, variable=self._fmt_var, value=fmt,
                           bg=BG_CARD, fg=TEXT_PRI, selectcolor=BG_INPUT,
                           activebackground=BG_CARD, activeforeground=ACCENT,
                           font=("Helvetica",10)).pack(side="left", padx=6)

        # Save path
        self._section(sb, "📁  SAVE LOCATION")
        prow = tk.Frame(sb, bg=BG_CARD)
        prow.pack(fill="x", padx=14, pady=(0,10))
        self._path_var = tk.StringVar(value=os.path.expanduser("~/Desktop"))
        path_entry = tk.Entry(prow, textvariable=self._path_var,
                              bg=BG_INPUT, fg=TEXT_PRI, insertbackground=ACCENT,
                              relief="flat", font=("Helvetica",9))
        path_entry.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Button(prow, text="…", command=self._browse,
                  bg=ACCENT, fg=BG_DARK, font=("Helvetica",9,"bold"),
                  relief="flat", padx=6, cursor="hand2").pack(side="left", padx=(4,0))

        # Stats box
        self._section(sb, "📊  SESSION STATS")
        sbox = tk.Frame(sb, bg=BG_INPUT, bd=0)
        sbox.pack(fill="x", padx=14, pady=(0,10))
        self._stat_vars = {}
        for k, v in [("Items Found","0"), ("Pages Done","0"), ("Errors","0"), ("Elapsed","0s")]:
            row = tk.Frame(sbox, bg=BG_INPUT)
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=k, font=("Helvetica",9), bg=BG_INPUT, fg=TEXT_SEC).pack(side="left")
            sv = tk.StringVar(value=v)
            self._stat_vars[k] = sv
            tk.Label(row, textvariable=sv, font=("Helvetica",9,"bold"),
                     bg=BG_INPUT, fg=ACCENT).pack(side="right")

        # Buttons
        spacer = tk.Frame(sb, bg=BG_CARD); spacer.pack(fill="both", expand=True)
        self._start_btn = self._big_btn(sb, "▶  START SCRAPING", ACCENT2, BG_DARK, self._start)
        self._stop_btn  = self._big_btn(sb, "⏹  STOP", ACCENT3, BG_DARK, self._stop)
        self._stop_btn.configure(state="disabled")
        self._export_btn = self._big_btn(sb, "💾  EXPORT DATA", ACCENT, BG_DARK, self._export)
        self._export_btn.configure(state="disabled")
        self._clear_btn  = self._big_btn(sb, "🗑  CLEAR ALL", TEXT_SEC, BG_DARK, self._clear)

    def _build_right(self, parent):
        rf = tk.Frame(parent, bg=BG_DARK)
        rf.grid(row=0, column=1, sticky="nsew", pady=4)
        rf.rowconfigure(1, weight=1)
        rf.columnconfigure(0, weight=1)

        # Progress bar + status
        pf = tk.Frame(rf, bg=BG_CARD)
        pf.grid(row=0, column=0, sticky="ew", pady=(0,10))
        pf.columnconfigure(1, weight=1)

        self._status_lbl = tk.Label(pf, text="Ready to scrape.",
                                    font=("Helvetica",10), bg=BG_CARD, fg=TEXT_SEC)
        self._status_lbl.grid(row=0, column=0, columnspan=3, padx=14, pady=(10,4), sticky="w")

        self._prog_var = tk.DoubleVar(value=0)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Scrape.Horizontal.TProgressbar",
                        troughcolor=BG_INPUT, background=ACCENT,
                        borderwidth=0, thickness=6)
        pb = ttk.Progressbar(pf, variable=self._prog_var, maximum=100,
                             style="Scrape.Horizontal.TProgressbar", mode="determinate")
        pb.grid(row=1, column=0, columnspan=3, padx=14, pady=(0,10), sticky="ew")

        self._prog_lbl = tk.Label(pf, text="0%", font=("Helvetica",9),
                                  bg=BG_CARD, fg=ACCENT)
        self._prog_lbl.grid(row=1, column=3, padx=(0,14))

        # Table
        tf = tk.Frame(rf, bg=BG_CARD)
        tf.grid(row=1, column=0, sticky="nsew")
        tf.rowconfigure(1, weight=1)
        tf.columnconfigure(0, weight=1)

        thead = tk.Frame(tf, bg=BG_CARD)
        thead.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10,4))
        tk.Label(thead, text="EXTRACTED PRODUCTS", font=("Helvetica",11,"bold"),
                 bg=BG_CARD, fg=TEXT_PRI).pack(side="left")
        self._count_lbl = tk.Label(thead, text="0 items", font=("Helvetica",9),
                                   bg=BG_CARD, fg=TEXT_SEC)
        self._count_lbl.pack(side="right")

        # Search bar
        srow = tk.Frame(tf, bg=BG_CARD)
        srow.grid(row=0, column=0, columnspan=2, sticky="e", padx=14)
        tk.Label(srow, text="🔍", bg=BG_CARD, fg=TEXT_SEC).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_table())
        se = tk.Entry(srow, textvariable=self._search_var,
                      bg=BG_INPUT, fg=TEXT_PRI, insertbackground=ACCENT,
                      relief="flat", font=("Helvetica",9), width=22)
        se.pack(side="left", ipady=4, padx=(2,0))

        # Treeview
        cols = ("Name","Price","Rating","Category","Scraped At")
        style.configure("Dark.Treeview",
                        background=BG_CARD, foreground=TEXT_PRI,
                        fieldbackground=BG_CARD, rowheight=28,
                        borderwidth=0, font=("Helvetica",9))
        style.configure("Dark.Treeview.Heading",
                        background=BG_INPUT, foreground=ACCENT,
                        relief="flat", font=("Helvetica",9,"bold"))
        style.map("Dark.Treeview",
                  background=[("selected", HOVER)],
                  foreground=[("selected", TEXT_PRI)])

        self._tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style="Dark.Treeview", selectmode="extended")
        for c, w in zip(cols, [320,100,80,100,130]):
            self._tree.heading(c, text=c,
                               command=lambda col=c: self._sort_col(col))
            self._tree.column(c, width=w, minwidth=60)

        vsb = ttk.Scrollbar(tf, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal",  command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=1, column=0, sticky="nsew", padx=(14,0), pady=(0,0))
        vsb.grid(row=1, column=1, sticky="ns",  pady=(0,0), padx=(0,4))
        hsb.grid(row=2, column=0, sticky="ew",  padx=(14,0))

        # Log panel
        lf = tk.Frame(rf, bg=BG_CARD)
        lf.grid(row=2, column=0, sticky="ew", pady=(10,0))
        lf.columnconfigure(0, weight=1)
        tk.Label(lf, text="ACTIVITY LOG", font=("Helvetica",9,"bold"),
                 bg=BG_CARD, fg=TEXT_SEC).grid(row=0, column=0, sticky="w", padx=14, pady=(8,2))
        self._log = tk.Text(lf, height=6, bg=BG_INPUT, fg=TEXT_SEC,
                            insertbackground=ACCENT, relief="flat",
                            font=("Courier",8), wrap="word", state="disabled")
        self._log.grid(row=1, column=0, sticky="ew", padx=14, pady=(0,10))
        self._log.tag_configure("ok",   foreground=ACCENT2)
        self._log.tag_configure("err",  foreground=ACCENT3)
        self._log.tag_configure("info", foreground=ACCENT)
        self._log.tag_configure("warn", foreground=WARN)

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BORDER, height=1); f.pack(fill="x", padx=14, pady=(12,0))
        tk.Label(parent, text=text, font=("Helvetica",8,"bold"),
                 bg=BG_CARD, fg=TEXT_SEC).pack(anchor="w", padx=14, pady=(4,4))

    def _slider_row(self, parent, label, var, lo, hi, resolution=1):
        row = tk.Frame(parent, bg=BG_CARD); row.pack(fill="x", padx=14, pady=(0,6))
        tk.Label(row, text=label, font=("Helvetica",9),
                 bg=BG_CARD, fg=TEXT_PRI).pack(side="left")
        vl = tk.Label(row, textvariable=var, font=("Helvetica",9,"bold"),
                      bg=BG_CARD, fg=ACCENT, width=4)
        vl.pack(side="right")
        sl = tk.Scale(parent, variable=var, from_=lo, to=hi, orient="horizontal",
                      resolution=resolution, showvalue=False,
                      bg=BG_CARD, fg=ACCENT, troughcolor=BG_INPUT,
                      activebackground=HOVER, highlightthickness=0, bd=0)
        sl.pack(fill="x", padx=14, pady=(0,2))

    def _big_btn(self, parent, text, bg, fg, cmd):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=bg, fg=fg, font=("Helvetica",10,"bold"),
                      relief="flat", bd=0, padx=10, pady=9,
                      activebackground=HOVER, activeforeground=TEXT_PRI,
                      cursor="hand2")
        b.pack(fill="x", padx=14, pady=3)
        return b

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_site_change(self, *_):
        self._log_msg(f"Site changed to: {self._site_var.get().split('(')[0].strip()}", "info")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._path_var.get())
        if d: self._path_var.set(d)

    def _tick_clock(self):
        self._clock_lbl.configure(text=datetime.now().strftime("🕐  %H:%M:%S   %d %b %Y"))
        self.after(1000, self._tick_clock)

    def _log_msg(self, msg, tag="info"):
        self._log.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] {msg}\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_status(self, msg, color=TEXT_SEC):
        self._status_lbl.configure(text=msg, fg=color)

    def _set_progress(self, pct):
        self._prog_var.set(pct)
        self._prog_lbl.configure(text=f"{int(pct)}%")

    def _update_stats(self, items=None, pages=None, errors=None, elapsed=None):
        if items   is not None: self._stat_vars["Items Found"].set(str(items))
        if pages   is not None: self._stat_vars["Pages Done"].set(str(pages))
        if errors  is not None: self._stat_vars["Errors"].set(str(errors))
        if elapsed is not None: self._stat_vars["Elapsed"].set(elapsed)

    # ── Table helpers ─────────────────────────────────────────────────────────

    def _rebuild_table(self, products):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for i, p in enumerate(products):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert("", "end", values=(
                p.get("Name",""), p.get("Price","N/A"),
                p.get("Rating","N/A"), p.get("Category",""),
                p.get("Scraped At","")), tags=(tag,))
        self._tree.tag_configure("odd",  background=BG_CARD)
        self._tree.tag_configure("even", background="#1C2128")
        self._count_lbl.configure(text=f"{len(products)} items")

    def _filter_table(self):
        q = self._search_var.get().lower()
        filtered = [p for p in self._products
                    if q in p.get("Name","").lower()
                    or q in p.get("Category","").lower()
                    or q in p.get("Price","").lower()]
        self._rebuild_table(filtered)

    def _sort_col(self, col):
        self._products.sort(key=lambda x: x.get(col,""), reverse=False)
        self._rebuild_table(self._products)

    # ── Scraping Logic ────────────────────────────────────────────────────────

    def _start(self):
        self._stop_flag = False
        self._products  = []
        self._rebuild_table([])
        self._update_stats(0, 0, 0, "0s")
        self._set_progress(0)
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._export_btn.configure(state="disabled")
        self._thread = threading.Thread(target=self._scrape_worker, daemon=True)
        self._thread.start()

    def _stop(self):
        self._stop_flag = True
        self._log_msg("Stop requested — finishing current page…", "warn")
        self._stop_btn.configure(state="disabled")

    def _scrape_worker(self):
        site   = self._site_var.get()
        cfg    = SITE_CONFIGS[site]
        parser = PARSERS[site]
        pages  = self._pages_var.get()
        delay  = self._delay_var.get()
        errors = 0
        start  = time.time()

        url  = cfg["home"]
        page = 0

        self._log_msg(f"Starting scrape of {site.split('(')[0].strip()}…", "info")
        self._set_status("Connecting…", ACCENT)

        while url and page < pages and not self._stop_flag:
            page += 1
            self._set_status(f"Scraping page {page} / {pages}…", ACCENT)
            self._log_msg(f"Fetching: {url}", "info")

            try:
                resp = requests.get(url, headers=HEADERS, timeout=12)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                items = parser(soup, cfg)
                self._products.extend(items)

                elapsed = int(time.time() - start)
                self._update_stats(
                    items  = len(self._products),
                    pages  = page,
                    errors = errors,
                    elapsed= f"{elapsed}s",
                )
                self._set_progress(min(100, page / pages * 100))
                self._rebuild_table(self._products)
                self._log_msg(f"  ✓ Got {len(items)} items (total {len(self._products)})", "ok")

                # Next page
                nxt = soup.select_one(cfg["next_sel"]) if cfg["next_sel"] else None
                if nxt:
                    href = nxt["href"]
                    if href.startswith("http"):
                        url = href
                    elif href.startswith("catalogue/") or href.startswith("/catalogue/"):
                        url = cfg["base_url"] + href.lstrip("/").replace("catalogue/","")
                    else:
                        url = cfg["base_url"] + href
                else:
                    url = None

                time.sleep(delay + random.uniform(0, 0.3))

            except Exception as e:
                errors += 1
                self._update_stats(errors=errors)
                self._log_msg(f"  ✗ Error on page {page}: {e}", "err")
                break

        self._set_progress(100)
        elapsed = int(time.time() - start)
        self._update_stats(elapsed=f"{elapsed}s")
        if self._stop_flag:
            self._set_status(f"Stopped. {len(self._products)} items collected.", WARN)
            self._log_msg("Scrape stopped by user.", "warn")
        else:
            self._set_status(f"Done! {len(self._products)} items in {elapsed}s.", ACCENT2)
            self._log_msg(f"Scrape complete — {len(self._products)} items in {elapsed}s.", "ok")

        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        if self._products:
            self._export_btn.configure(state="normal")

    # ── Export ────────────────────────────────────────────────────────────────

    def _export(self):
        if not self._products:
            messagebox.showinfo("No Data", "Nothing to export yet.")
            return
        fmt   = self._fmt_var.get()
        path  = self._path_var.get()
        site  = self._site_var.get().split("(")[1].rstrip(")")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base  = os.path.join(path, f"scraped_{site}_{stamp}")

        saved = []
        if fmt in ("CSV","Both"):
            fp = base + ".csv"
            keys = list(self._products[0].keys())
            with open(fp, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader(); w.writerows(self._products)
            saved.append(fp)
        if fmt in ("JSON","Both"):
            fp = base + ".json"
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(self._products, f, indent=2, ensure_ascii=False)
            saved.append(fp)

        self._log_msg(f"Exported {len(self._products)} items → {', '.join(saved)}", "ok")
        msg = f"Saved {len(self._products)} items:\n" + "\n".join(saved)
        if messagebox.askyesno("Export Successful", msg + "\n\nOpen containing folder?"):
            webbrowser.open(f"file://{path}")

    def _clear(self):
        if self._products and not messagebox.askyesno("Clear All", "Delete all scraped data?"):
            return
        self._products = []
        self._rebuild_table([])
        self._update_stats(0,0,0,"0s")
        self._set_progress(0)
        self._set_status("Ready to scrape.", TEXT_SEC)
        self._export_btn.configure(state="disabled")
        self._log_msg("Data cleared.", "warn")


if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()
