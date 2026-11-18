from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QHBoxLayout, QListWidget, QListWidgetItem, QProgressBar,
                               QSpinBox, QVBoxLayout, QWidget)

import pokopia_save as ps
from gui import theme as T
from gui import widgets as W
from gui.pages.base import Page

KINDS = (('dex', 'Pokédex', 'people', 'Register all'),
         ('habitat', 'Habitats', 'map', 'Mark all built'),
         ('recipe', 'Crafting', 'layers', 'Learn all'),
         ('cooking', 'Cooking', 'gift', 'Learn all'),
         ('frame', 'Photo frames', 'photo', 'Unlock all'),
         ('filter', 'Photo filters', 'camera', 'Unlock all'),
         ('item', 'Item list', 'bag', 'Mark all obtained'),
         ('record', 'Human Records', 'list', 'Collect all'),
         ('artifact', 'Ancient Artifacts', 'pin', 'Collect all'),
         ('photoop', 'Highlight Reel', 'play', 'Complete all'))
PARTIAL = {'dex': 'Mark seen', 'habitat': 'Mark discovered'}
COMPLETE = {'dex': 'Register', 'habitat': 'Mark built', 'recipe': 'Learn', 'cooking': 'Learn', 'frame': 'Unlock',
            'filter': 'Unlock', 'item': 'Mark obtained', 'record': 'Collect', 'artifact': 'Collect',
            'photoop': 'Complete'}
ICON = 30


class CollectionPage(Page):
    title, nav, glyph = 'Collection', 'Collection', T.G['star']
    subtitle = 'Complete the Pokédex, habitats, recipes, item list, records, artifacts, photo styles and upgrades'
    scrollable = True

    def build(self):
        lay = QVBoxLayout(self.root)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(14)
        self.kind, self.filled = 'dex', None

        # summary: one small card per collection
        grid = QGridLayout()
        grid.setSpacing(14)
        self.sum = {}
        for n, (kind, title, glyph, action) in enumerate(KINDS):
            card = W.Card(title, '', T.G[glyph], padding=14, spacing=8)
            bar = QProgressBar()
            bar.setTextVisible(False)
            b = W.button(action, T.G['unlock'], lambda k=kind: self.unlock_all(k), small=True)
            card.body.addWidget(bar)
            card.body.addWidget(b, 0, Qt.AlignLeft)
            grid.addWidget(card, n // 3, n % 3)
            self.sum[kind] = (card, bar, b)
        lay.addLayout(grid)

        allc = W.Card('Everything', 'Completes every list above in one step. Upgrades and Life Coins are separate, below.',
                      T.G['star'])
        self.all_btn = W.button('Unlock everything', T.G['unlock'], self.unlock_everything, accent=True)
        allc.actions.addWidget(self.all_btn)
        lay.addWidget(allc)

        # browser: pick single entries
        br = W.Card('Browse', '', T.G['list'])
        self.browse = br
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chips = {}
        for kind, title, _, _ in KINDS:
            c = W.chip(title, slot=lambda k=kind: self.set_kind(k))
            chips.addWidget(c)
            self.chips[kind] = c
        chips.addStretch(1)
        self.missing = W.chip('Missing only', slot=self.fill)
        chips.addWidget(self.missing)
        br.body.addLayout(chips)
        self.q = W.SearchField('Search this list')
        self.q.textChanged.connect(lambda *_: self.fill())
        br.body.addWidget(self.q)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setUniformItemSizes(True)
        self.list.setIconSize(QSize(ICON, ICON))
        self.list.setFixedHeight(380)
        self.list.setStyleSheet('QListWidget::item { padding: 3px 8px; border-radius: 8px; border: none; margin: 0; }'
                                f'QListWidget::item:selected {{ background: {T.P["sel"]}; color: {T.P["text"]}; }}'
                                f'QListWidget::item:hover:!selected {{ background: {T.P["tilehi"]}; }}')
        self.list.itemSelectionChanged.connect(self.update_buttons)
        self.list.itemDoubleClicked.connect(lambda *_: self.unlock_selected(False))
        br.body.addWidget(self.list)
        self.b_full = W.button('Unlock', T.G['unlock'], lambda: self.unlock_selected(False), accent=True)
        self.b_part = W.button('Mark seen', T.G['check'], lambda: self.unlock_selected(True))
        self.sel_lbl = W.label('', 'muted')
        br.body.addLayout(W.hbox(self.sel_lbl, 1, self.b_part, self.b_full))
        lay.addWidget(br)

        # upgrades (function flags)
        up = W.Card('Upgrades & features', 'Bag and PP upgrades, Jump, painting and Poké Center PC features. Switching one '
                    'on also switches on what it builds on.', T.G['flag'])
        g = QGridLayout()
        g.setHorizontalSpacing(28)
        g.setVerticalSpacing(4)
        self.up_w = {}
        for n, (key, (label, _, _)) in enumerate(ps.UPGRADES.items()):
            row = W.ToggleRow(label)
            row.toggle.toggled.connect(lambda on, k=key: self.toggle_upgrade(k, on))
            g.addWidget(row, n // 4, n % 4)
            self.up_w[key] = row
        up.body.addLayout(g)
        self.up_all = W.button('Switch all on', T.G['unlock'], self.all_upgrades)
        up.actions.addWidget(self.up_all)
        up.body.addWidget(W.label('These are story switches the game normally sets itself. Their meaning has not '
                                  'been checked in game by this editor: keep a backup, and switch one off '
                                  'again if something looks wrong.', 'small', wrap=True))
        lay.addWidget(up)

        co = W.Card('Life Coins', '', T.G['gift'])
        self.coins_card = co
        self.coins = QSpinBox()
        self.coins.setRange(0, ps.COINS_MAX)
        self.coins.setSingleStep(1000)
        self.coins.setGroupSeparatorShown(True)
        self.coins.setFixedWidth(130)
        co.actions.addWidget(self.coins)
        co.actions.addWidget(W.button('Set', T.G['check'], self.set_coins, accent=True))
        co.actions.addWidget(W.button('Max', slot=lambda: (self.coins.setValue(ps.COINS_MAX), self.set_coins())))
        lay.addWidget(co)

        lay.addWidget(W.label(
            'Bubbly Basin Pokémon and habitats are counted on their own tab in the game, so its main totals stay lower '
            'than the ones here. Marking an item obtained fills the item list; it does not put the item in your bag. '
            'A Highlight Reel entry completed here has no photo of its own. '
            'The lists only ever gain entries here; use Undo (or a backup) to take something back. Registering a Pokémon '
            'fills its Pokédex page but does not make it move in, and marking a habitat built does not place it on the '
            'island. Crafting recipes are added after the ones you already know, in list order.', 'muted', wrap=True))
        lay.addStretch(1)
        self.chips['dex'].setChecked(True)

    # ---------- state ----------
    def refresh(self):
        c = self.c
        if not c:
            return
        left = 0
        for kind, title, _, _ in KINDS:
            card, bar, b = self.sum[kind]
            total = len(ps.COLLECTION[kind])
            full, part = c.collection_count(kind), c.collection_count(kind, 1)
            _, pname, fname = ps.COLLECTION_INFO[kind]
            extra = f' · {part - full} {pname}' if part > full and pname else ''
            card.set_subtitle(f'{full} of {total} {fname}{extra}')
            bar.setRange(0, total)
            bar.setValue(full)
            b.setEnabled(full < total)
            left += total - full
        self.all_btn.setEnabled(left > 0)
        for key, row in self.up_w.items():
            row.toggle.set_quiet(c.upgrade(key))
        self.up_all.setEnabled(not all(c.upgrade(k) for k in ps.UPGRADES))
        self.coins_card.set_subtitle(f'{c.coins:,} in the save')
        self.coins.setValue(max(0, min(ps.COINS_MAX, c.coins)))
        self.fill()

    def icon(self, kind, i):
        a = self.app.assets
        if kind == 'dex':
            r = ps.DEX_RESIDENT[i] if i < len(ps.DEX_RESIDENT) else 0
            pm = a.villager(r, ICON) if r else None
        elif ps.collection_item(kind, i):
            pm = a.item(ps.collection_item(kind, i), ICON)
        else:
            pm = None
        return QIcon(pm) if pm else None

    def set_kind(self, kind):
        self.kind = kind
        for k, c in self.chips.items():
            c.setChecked(k == kind)
        self.q.clear()
        self.fill()

    def fill(self):
        c = self.c
        if not c:
            return
        kind = self.kind
        _, pname, fname = ps.COLLECTION_INFO[kind]
        text = self.q.text().strip().lower()
        keep = {it.data(Qt.UserRole) for it in self.list.selectedItems()} if self.filled == kind else set()
        scroll = self.list.verticalScrollBar().value() if self.filled == kind else 0
        self.list.blockSignals(True)
        self.list.clear()
        for i, name in ps.COLLECTION[kind]:
            st = c.collection_state(kind, i)
            if (self.missing.isChecked() and st == 2) or (text and text not in name.lower()):
                continue
            num = f'#{i:03}  ' if kind in ('dex', 'habitat') else ''
            status = fname if st == 2 else pname if st == 1 else '—'
            it = QListWidgetItem(f'{num}{name}    ·    {status}')
            it.setData(Qt.UserRole, i)
            ic = self.icon(kind, i)
            if ic:
                it.setIcon(ic)
            if st == 0:
                it.setForeground(QColor(T.P['muted']))
            elif st == 2:
                it.setForeground(QColor(T.P['accent']))
            self.list.addItem(it)
            if i in keep:
                it.setSelected(True)
        self.list.blockSignals(False)
        self.list.verticalScrollBar().setValue(scroll)
        self.filled = kind
        total = len(ps.COLLECTION[kind])
        self.browse.set_subtitle(f'{ps.COLLECTION_INFO[kind][0]}: showing {self.list.count()} of {total}. Select entries '
                                 '(Ctrl or Shift for several) or double-click one.')
        self.update_buttons()

    def selected(self):
        return [it.data(Qt.UserRole) for it in self.list.selectedItems()]

    def update_buttons(self):
        c, kind, ids = self.c, self.kind, self.selected()
        self.b_full.setText(COMPLETE[kind])
        self.b_part.setVisible(kind in PARTIAL)
        self.b_part.setText(PARTIAL.get(kind, ''))
        states = [c.collection_state(kind, i) for i in ids] if c else []
        self.b_full.setEnabled(any(s < 2 for s in states))
        self.b_part.setEnabled(any(s < 1 for s in states))
        self.sel_lbl.setText(f'{len(ids)} selected' if ids else '')

    # ---------- edits ----------
    def unlock_all(self, kind):
        title = ps.COLLECTION_INFO[kind][0]
        self.app.do(f'Complete {title}', lambda: self.c.unlock_collection(kind))

    def unlock_everything(self):
        self.app.do('Unlock everything', lambda: [self.c.unlock_collection(k) for k in ps.COLLECTION])

    def unlock_selected(self, partial):
        ids, kind = self.selected(), self.kind
        if not ids or not self.app.need():
            return
        names = dict(ps.COLLECTION[kind])
        what = names[ids[0]] if len(ids) == 1 else f'{len(ids)} entries'
        verb = (PARTIAL if partial else COMPLETE)[kind]
        self.app.do(f'{verb}: {what}', lambda: self.c.unlock_collection(kind, ids, partial))

    def toggle_upgrade(self, key, on):
        if not self.app.need():
            return
        label = ps.UPGRADES[key][0]
        self.app.do(f'{label}: {"on" if on else "off"}', lambda: self.c.set_upgrade(key, on))

    def all_upgrades(self):
        self.app.do('Switch all upgrades on', lambda: [self.c.set_upgrade(k) for k in ps.UPGRADES])

    def set_coins(self):
        v = self.coins.value()
        if self.app.need() and v != self.c.coins:
            def go():
                self.c.coins = v
            self.app.do(f'Life Coins: {v:,}', go)
