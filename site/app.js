"use strict";

// Adresse affichée pour les corrections et les demandes de retrait.
const CONTACT = "arbre.parrains.centralelille@gmail.com";

// Dimensions de l'arbre (en pixels SVG)
const NOEUD_L = 92, NOEUD_H = 46, ECART_X = 11, RANGEE = 86, RAYON_LIEN = 10;
const FOCUS_PLUS = { l: 12, h: 8 };        // la personne choisie est un peu plus grande
const MARGE_RAIL = 104;                    // place à gauche pour les années de promo
const TELEPHONE = "(max-width: 699px)";

const $ = (sel) => document.querySelector(sel);
const etat = { personnes: new Map(), fillots: new Map(), promos: {}, zoom: null, focus: null };

// --- Données ----------------------------------------------------------------

function normaliser(s) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-–—'’._]/g, " ").trim();
}

function nomComplet(p) {
  return p.inconnu ? "Inconnu·e" : [p.prenom, p.nom].filter(Boolean).join(" ");
}

function libellePromo(promo) {
  const nom = etat.promos[promo];
  return nom ? `Promo ${promo} · ${nom}` : `Promo ${promo}`;
}

function initiales(p) {
  if (p.inconnu) return "?";
  return [p.prenom, p.nom].filter(Boolean).map((s) => s.trim()[0] || "").join("").toUpperCase();
}

async function charger() {
  const rep = await fetch("data/arbre.json", { cache: "no-cache" });
  if (!rep.ok) throw new Error(`HTTP ${rep.status}`);
  const donnees = await rep.json();
  etat.promos = donnees.promos;
  for (const p of donnees.personnes) {
    p.mots = normaliser(nomComplet(p)).split(/\s+/);
    etat.personnes.set(p.id, p);
    etat.fillots.set(p.id, []);
  }
  for (const p of donnees.personnes) {
    if (p.parrain != null && etat.fillots.has(p.parrain)) etat.fillots.get(p.parrain).push(p);
  }
  for (const liste of etat.fillots.values()) liste.sort(parNom);
  return donnees;
}

const parNom = (a, b) => nomComplet(a).localeCompare(nomComplet(b), "fr");
const parrainDe = (p) => (p.parrain != null ? etat.personnes.get(p.parrain) : null);

function ancetres(p) {
  const liste = [];
  for (let a = parrainDe(p); a && !liste.includes(a); a = parrainDe(a)) liste.push(a);
  return liste;
}

function descendants(p, acc = []) {
  for (const f of etat.fillots.get(p.id)) { acc.push(f); descendants(f, acc); }
  return acc;
}

// --- Recherche ----------------------------------------------------------------

// Distance d'édition bornée : tolère une faute de frappe sur les mots assez longs.
function prochesA1(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  let i = 0, j = 0, fautes = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { i++; j++; continue; }
    if (++fautes > 1) return false;
    if (a.length > b.length) i++;
    else if (b.length > a.length) j++;
    else { i++; j++; }
  }
  return fautes + (a.length - i) + (b.length - j) <= 1;
}

function rechercher(requete) {
  const termes = normaliser(requete).split(/\s+/).filter(Boolean);
  if (!termes.length) return [];
  const resultats = [];
  for (const p of etat.personnes.values()) {
    if (p.inconnu) continue;
    let score = 0;
    for (const t of termes) {
      if (p.mots.some((m) => m === t)) score += 3;
      else if (p.mots.some((m) => m.startsWith(t))) score += 2;
      else if (t.length >= 4 && p.mots.some((m) => prochesA1(m.slice(0, t.length + 1), t) || prochesA1(m, t))) score += 1;
      else { score = 0; break; }
    }
    if (score) resultats.push({ p, score });
  }
  resultats.sort((a, b) => b.score - a.score || b.p.promo - a.p.promo || parNom(a.p, b.p));
  return resultats.slice(0, 12).map((r) => r.p);
}

// Nom avec, en surbrillance, le début de chaque mot qui correspond à la recherche.
function nomSurligne(p, requete) {
  const termes = normaliser(requete).split(/\s+/).filter(Boolean);
  const span = document.createElement("span");
  span.className = "nom";
  const morceaux = nomComplet(p).split(/(\s+)/);
  for (const morceau of morceaux) {
    const norm = normaliser(morceau);
    const t = termes.filter((t) => norm.startsWith(t)).sort((a, b) => b.length - a.length)[0];
    // La normalisation garde une lettre par lettre (accents retirés) : les positions concordent.
    if (t && norm.length === morceau.length) {
      const mark = document.createElement("mark");
      mark.textContent = morceau.slice(0, t.length);
      span.append(mark, morceau.slice(t.length));
    } else span.append(morceau);
  }
  return span;
}

function sousTitre(p) {
  const parrain = parrainDe(p);
  const promo = etat.promos[p.promo] || `Promo ${p.promo}`;
  return `${promo} · ${parrain ? `fillot·e de ${nomComplet(parrain)}` : "fondateur·rice de famille"}`;
}

function initRecherche(champ, liste) {
  let items = [], actif = -1;

  const fermer = () => { liste.hidden = true; champ.setAttribute("aria-expanded", "false"); actif = -1; };
  const choisir = (p) => { fermer(); champ.value = ""; champ.blur(); allerA(p.id); };
  const surligner = () => [...liste.children].forEach((li, i) => {
    li.setAttribute("aria-selected", i === actif);
    if (i === actif) li.scrollIntoView({ block: "nearest" });
  });

  champ.addEventListener("input", () => {
    items = rechercher(champ.value);
    liste.replaceChildren();
    if (!champ.value.trim()) return fermer();
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "vide";
      li.textContent = "Aucun résultat";
      liste.appendChild(li);
    }
    items.forEach((p, i) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.id = `${liste.id}-${i}`;
      const annee = document.createElement("span");
      annee.className = "annee";
      annee.setAttribute("aria-hidden", "true");
      annee.textContent = p.promo;
      const qui = document.createElement("span");
      qui.className = "qui";
      const sous = document.createElement("span");
      sous.className = "sous";
      sous.textContent = sousTitre(p);
      qui.append(nomSurligne(p, champ.value), sous);
      li.append(annee, qui);
      li.addEventListener("mousedown", (e) => { e.preventDefault(); choisir(p); });
      liste.appendChild(li);
    });
    actif = items.length ? 0 : -1;
    surligner();
    liste.hidden = false;
    champ.setAttribute("aria-expanded", "true");
  });

  champ.addEventListener("keydown", (e) => {
    if (liste.hidden) return;
    if (e.key === "ArrowDown") { actif = Math.min(actif + 1, items.length - 1); surligner(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { actif = Math.max(actif - 1, 0); surligner(); e.preventDefault(); }
    else if (e.key === "Enter" && items[actif]) choisir(items[actif]);
    else if (e.key === "Escape") fermer();
  });
  champ.addEventListener("blur", fermer);
}

// --- Navigation (l'URL #p=123 rend chaque arbre partageable) -------------------

function allerA(id) { location.hash = `p=${id}`; }

function lireHash() {
  const m = location.hash.match(/^#p=(\d+)$/);
  const p = m && etat.personnes.get(Number(m[1]));
  $("#accueil").hidden = !!p;
  $("#vue").hidden = !p;
  document.body.classList.toggle("mode-accueil", !p);
  document.body.classList.toggle("mode-arbre", !!p);
  if (p) afficher(p);
  else document.title = "Arbre des parrains · Centrale Lille";
}

// --- Fiche (carte de la personne) --------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";

function remplirFiche(p, racine, taille, generations) {
  const fiche = $("#fiche");
  fiche.replaceChildren();

  const identite = document.createElement("div");
  identite.className = "identite";
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.setAttribute("aria-hidden", "true");
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 200 200");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#decagone");
  svg.appendChild(use);
  const ini = document.createElement("span");
  ini.textContent = initiales(p);
  badge.append(svg, ini);

  const bloc = document.createElement("div");
  const h2 = document.createElement("h2");
  h2.textContent = nomComplet(p);
  const promo = document.createElement("p");
  promo.className = "promo";
  promo.textContent = libellePromo(p.promo);
  // Version courte, affichée seulement sur téléphone (bandeau du bas).
  const court = document.createElement("p");
  court.className = "court";
  court.textContent = [p.promo, etat.promos[p.promo], `famille de ${taille}`].filter(Boolean).join(" · ");
  bloc.append(h2, promo, court);
  identite.append(badge, bloc);

  const fam = document.createElement("p");
  fam.className = "famille";
  if (racine === p && taille === 1) {
    fam.textContent = "Pas encore de parrain ni de fillot dans l'arbre.";
  } else {
    fam.append("Famille de ");
    const b = document.createElement("b");
    b.textContent = `${taille} personnes`;
    fam.append(b, ` sur ${generations} promos, fondée par ${nomComplet(racine)}.`);
  }

  const legende = document.createElement("ul");
  legende.className = "legende";
  legende.innerHTML = '<li><span class="l-lignee"></span>Lignée</li><li><span class="l-fratrie"></span>Co-fillot·e</li>';

  const signaler = document.createElement("a");
  signaler.className = "signaler contact";
  signaler.href = lienContact();
  signaler.textContent = "Une erreur ? Écris-nous";

  fiche.append(identite, fam, legende, signaler);
}

// --- Arbre ------------------------------------------------------------------------

// Coupe un texte SVG avec « … » pour qu'il tienne dans la largeur donnée.
function ajuster(texte, largeur) {
  const el = texte.node();
  let s = el.textContent;
  if (el.getComputedTextLength() <= largeur) return;
  while (s.length > 1 && el.getComputedTextLength() > largeur) {
    s = s.slice(0, -1);
    el.textContent = s.trimEnd() + "…";
  }
}

// Lien coudé parrain -> fillot, aux angles arrondis.
function coude(x1, y1, ym, x2, y2) {
  const dx = x2 - x1;
  if (Math.abs(dx) < 0.5) return `M${x1},${y1}V${y2}`;
  const s = Math.sign(dx), r = Math.min(RAYON_LIEN, Math.abs(dx) / 2, Math.abs(ym - y1), Math.abs(y2 - ym));
  return `M${x1},${y1}V${ym - r}Q${x1},${ym} ${x1 + s * r},${ym}H${x2 - s * r}Q${x2},${ym} ${x2},${ym + r}V${y2}`;
}

function afficher(p) {
  etat.focus = p;
  document.title = `${nomComplet(p)} · Arbre des parrains`;

  const lignee = ancetres(p);
  const racine = lignee.length ? lignee[lignee.length - 1] : p;
  const lignee_ids = new Set([p.id, ...lignee.map((a) => a.id), ...descendants(p).map((d) => d.id)]);
  const parrain = parrainDe(p);
  const fratrie_ids = new Set(parrain ? etat.fillots.get(parrain.id).map((f) => f.id) : []);
  const role = (id) => id === p.id ? "focus" : lignee_ids.has(id) ? "lignee" : fratrie_ids.has(id) ? "fratrie" : "autre";

  // Chaque rangée correspond à une promo (et pas seulement à une génération) :
  // un parrain redoublant apparaît deux rangées au-dessus de son fillot. Pour que la
  // mise en page réserve la place du lien, on insère un nœud « fantôme » invisible
  // dans chaque promo sautée.
  const emballer = (promoParent, f) => {
    let n = f;
    for (let pr = f.promo - 1; pr > promoParent; pr--) n = { fantome: true, promo: pr, suite: n };
    return n;
  };
  const h = d3.hierarchy(racine, (d) =>
    d.fantome ? [d.suite] : etat.fillots.get(d.id).map((f) => emballer(d.promo, f)));
  d3.tree().nodeSize([NOEUD_L + ECART_X, RANGEE])
    .separation((a, b) => (a.parent === b.parent ? 1 : 1.15))(h);
  h.each((d) => { d.y = (d.data.promo - racine.promo) * RANGEE; });

  const reel = (d) => { while (d.data.fantome) d = d.parent; return d; };
  const noeuds = h.descendants().filter((d) => !d.data.fantome);
  const promos = [...new Set(noeuds.map((d) => d.data.promo))].sort();
  const minX = d3.min(noeuds, (d) => d.x) - NOEUD_L / 2 - FOCUS_PLUS.l / 2;
  const maxX = d3.max(noeuds, (d) => d.x) + NOEUD_L / 2 + FOCUS_PLUS.l / 2;
  const derniere = promos[promos.length - 1];
  remplirFiche(p, racine, noeuds.length, derniere - promos[0] + 1);

  const svg = d3.select("#arbre");
  svg.selectAll("*").remove();
  const g = svg.append("g");

  // Rail des promos : grande année et nom de promo à gauche, filet fin sur toute la largeur.
  const xRail = minX - MARGE_RAIL;
  const rail = g.append("g").attr("class", "rail").selectAll("g")
    .data(d3.range(racine.promo, derniere + 1)).join("g")
    .attr("transform", (pr) => `translate(0,${(pr - racine.promo) * RANGEE})`);
  rail.append("line").attr("x1", xRail + 72).attr("x2", maxX + 24);
  rail.append("text").attr("class", "annee").attr("x", xRail).attr("y", 2).text((pr) => pr);
  rail.append("text").attr("class", "nom-promo").attr("x", xRail).attr("y", 17)
    .text((pr) => etat.promos[pr] || "").each(function () { ajuster(d3.select(this), 76); });

  // Liens parrain -> fillot (coudés). Un lien qui traverse un fantôme est découpé en
  // segments qui passent par son centre.
  const idFinal = (data) => { while (data.fantome) data = data.suite; return data.id; };
  const demiH = (d) => (d.data.fantome ? 0 : (d.data.id === p.id ? NOEUD_H + FOCUS_PLUS.h : NOEUD_H) / 2);
  const liens = h.links().map((l) => ({
    ...l, lignee: lignee_ids.has(reel(l.source).data.id) && lignee_ids.has(idFinal(l.target.data)),
  })).sort((a, b) => a.lignee - b.lignee);   // la lignée est dessinée par-dessus
  g.append("g").selectAll("path").data(liens).join("path")
    .attr("class", (l) => "lien" + (l.lignee ? " lignee" : ""))
    .attr("d", (l) => coude(l.source.x, l.source.y + demiH(l.source), l.source.y + RANGEE / 2,
      l.target.x, l.target.y - demiH(l.target)));

  // Nœuds
  const n = g.append("g").selectAll("g").data(noeuds).join("g")
    .attr("class", (d) => `noeud ${role(d.data.id)}` + (d.data.inconnu ? " inconnu" : ""))
    .attr("transform", (d) => {
      const f = d.data.id === p.id;
      return `translate(${d.x - (NOEUD_L + (f ? FOCUS_PLUS.l : 0)) / 2},${d.y - (NOEUD_H + (f ? FOCUS_PLUS.h : 0)) / 2})`;
    })
    .attr("tabindex", 0)
    .attr("role", "link")
    .attr("aria-label", (d) => `${nomComplet(d.data)}, ${libellePromo(d.data.promo)}`)
    .on("click", (_, d) => allerA(d.data.id))
    .on("keydown", (e, d) => { if (e.key === "Enter") allerA(d.data.id); });
  const largeur = (d) => NOEUD_L + (d.data.id === p.id ? FOCUS_PLUS.l : 0);
  const hauteur = (d) => NOEUD_H + (d.data.id === p.id ? FOCUS_PLUS.h : 0);
  n.append("title").text((d) => `${nomComplet(d.data)} — ${libellePromo(d.data.promo)}`);
  n.append("rect").attr("class", "ombre").attr("x", (d) => (d.data.id === p.id ? 3 : 0)).attr("y", (d) => (d.data.id === p.id ? 3 : 1))
    .attr("width", largeur).attr("height", hauteur).attr("rx", 4);
  n.append("rect").attr("class", "case").attr("width", largeur).attr("height", hauteur).attr("rx", 4);
  n.append("text").attr("class", "prenom").attr("x", 8).attr("y", (d) => hauteur(d) / 2 - 3)
    .text((d) => (d.data.inconnu ? "?" : d.data.prenom || ""))
    .each(function (d) { ajuster(d3.select(this), largeur(d) - 16); });
  n.append("text").attr("class", "nom").attr("x", 8).attr("y", (d) => hauteur(d) / 2 + 12)
    .text((d) => (d.data.inconnu ? "Inconnu·e" : d.data.nom || ""))
    .each(function (d) { ajuster(d3.select(this), largeur(d) - 16); });

  // Boîte englobante (rail compris) et rectangles des cases, pour le placement et la mini-carte.
  etat.boite = { x: xRail - 16, y: -RANGEE / 2, l: maxX + 24 - (xRail - 16), h: (derniere - racine.promo + 1) * RANGEE };
  etat.cases = noeuds.map((d) => ({
    x: d.x - largeur(d) / 2, y: d.y - hauteur(d) / 2, l: largeur(d), h: hauteur(d), role: role(d.data.id),
  }));
  etat.noeudFocus = noeuds.find((d) => d.data.id === p.id);

  // Zoom et déplacement (souris, molette, doigts). Pas de bouton : on pince ou on fait glisser.
  etat.zoom = d3.zoom().scaleExtent([0.15, 2.5])
    .on("zoom", (e) => { g.attr("transform", e.transform); majMinicarte(e.transform); });
  svg.call(etat.zoom).on("dblclick.zoom", null);

  dessinerMinicarte();
  placerAuDepart();
}

// --- Placement de départ ------------------------------------------------------------
// La carte de la personne est attachée à l'écran. Au départ, on cherche le plus grand
// zoom (≤ 1) qui montre tout l'arbre sans qu'aucune case passe sous la carte :
// ailleurs dans l'écran, à droite de la carte, ou en dessous. Si l'arbre est trop grand
// pour rester lisible, on zoome sur la personne choisie, dans la zone libre.

function zoneCarte() {
  const fiche = $("#fiche"), vue = $("#vue");
  const a = vue.getBoundingClientRect(), b = fiche.getBoundingClientRect();
  return { x: b.left - a.left - 10, y: b.top - a.top - 10, l: b.width + 26, h: b.height + 26 };
}

function chevauche(cases, t, z) {
  return cases.some((c) => {
    const x = t.x + c.x * t.k, y = t.y + c.y * t.k, l = c.l * t.k, h = c.h * t.k;
    return x < z.x + z.l && x + l > z.x && y < z.y + z.h && y + h > z.y;
  });
}

function ajusterDans(zone, b, max = 1) {
  const k = Math.min(max, (zone.l - 24) / b.l, (zone.h - 24) / b.h);
  return { k, x: zone.x + (zone.l - b.l * k) / 2 - b.x * k, y: zone.y + (zone.h - b.h * k) / 2 - b.y * k };
}

function placerAuDepart() {
  const svg = d3.select("#arbre");
  const { width: L, height: H } = svg.node().getBoundingClientRect();
  const b = etat.boite, z = zoneCarte();
  const telephone = matchMedia(TELEPHONE).matches;
  const lisible = telephone ? 0.62 : 0.55;

  const zones = telephone
    ? [{ x: 0, y: 0, l: L, h: z.y }]                           // au-dessus du bandeau
    : [{ x: 0, y: 0, l: L, h: H },                             // tout l'écran
      { x: z.x + z.l, y: 0, l: L - z.x - z.l, h: H },          // à droite de la carte
      { x: 0, y: z.y + z.h, l: L, h: H - z.y - z.h }];         // sous la carte
  let meilleur = null;
  for (const zone of zones) {
    if (zone.l <= 0 || zone.h <= 0) continue;
    const t = ajusterDans(zone, b);
    if (t.k >= lisible && !chevauche(etat.cases, t, z) && (!meilleur || t.k > meilleur.k + 0.01)) meilleur = t;
  }
  if (!meilleur) {
    // Trop grand : zoom sur la personne, centrée dans la zone libre.
    const k = telephone ? 0.85 : 1;
    const libre = telephone ? { x: 0, y: 0, l: L, h: z.y } : { x: z.x + z.l, y: 0, l: L - z.x - z.l, h: H };
    const d = etat.noeudFocus;
    meilleur = { k, x: libre.x + libre.l / 2 - d.x * k, y: libre.y + libre.h * 0.45 - d.y * k };
  }
  svg.call(etat.zoom.transform, d3.zoomIdentity.translate(meilleur.x, meilleur.y).scale(meilleur.k));
}

// --- Mini-carte (visible quand l'arbre dépasse de l'écran) -----------------------------

const MINI_L = 116, MINI_HMAX = 96;

function dessinerMinicarte() {
  const b = etat.boite;
  const k = Math.min(MINI_L / b.l, MINI_HMAX / b.h);
  etat.mini = { k, l: b.l * k, h: b.h * k };
  const svg = d3.select("#minicarte svg").attr("width", etat.mini.l).attr("height", etat.mini.h);
  svg.selectAll("*").remove();
  const g = svg.append("g").attr("transform", `scale(${k}) translate(${-b.x},${-b.y})`);
  g.selectAll("rect").data(etat.cases).join("rect")
    .attr("class", (c) => `m-noeud ${c.role}`)
    .attr("x", (c) => c.x).attr("y", (c) => c.y)
    .attr("width", (c) => Math.max(c.l, 3 / k)).attr("height", (c) => Math.max(c.h, 2.5 / k)).attr("rx", 2 / k);
  etat.miniCadre = g.append("rect").attr("class", "m-cadre");
}

function majMinicarte(t) {
  const mini = $("#minicarte");
  if (!etat.mini || !etat.miniCadre) return;
  const { width: L, height: H } = $("#arbre").getBoundingClientRect();
  const b = etat.boite;
  const x0 = -t.x / t.k, y0 = -t.y / t.k, x1 = x0 + L / t.k, y1 = y0 + H / t.k;
  const toutVisible = x0 <= b.x + 1 && y0 <= b.y + 1 && x1 >= b.x + b.l - 1 && y1 >= b.y + b.h - 1;
  mini.hidden = toutVisible;
  if (toutVisible) return;
  const cx0 = Math.max(x0, b.x), cy0 = Math.max(y0, b.y);
  const cx1 = Math.min(x1, b.x + b.l), cy1 = Math.min(y1, b.y + b.h);
  etat.miniCadre.attr("x", cx0).attr("y", cy0)
    .attr("width", Math.max(0, cx1 - cx0)).attr("height", Math.max(0, cy1 - cy0));
}

function initMinicarte() {
  // Toucher la mini-carte centre l'arbre sur l'endroit touché.
  $("#minicarte").addEventListener("click", (e) => {
    const r = $("#minicarte svg").getBoundingClientRect();
    const b = etat.boite, k = etat.mini.k;
    const wx = b.x + (e.clientX - r.left) / k, wy = b.y + (e.clientY - r.top) / k;
    const svg = d3.select("#arbre");
    const t = d3.zoomTransform(svg.node());
    const { width: L, height: H } = svg.node().getBoundingClientRect();
    svg.transition().duration(350)
      .call(etat.zoom.transform, d3.zoomIdentity.translate(L / 2 - wx * t.k, H / 2 - wy * t.k).scale(t.k));
  });
}

// --- Démarrage ----------------------------------------------------------------------

function lienContact() {
  return `mailto:${CONTACT}?subject=${encodeURIComponent("Arbre des parrains")}`;
}

function tuile(classe, nombre, libelle) {
  const div = document.createElement("div");
  div.className = `tuile ${classe}`;
  const b = document.createElement("b");
  b.textContent = nombre;
  const span = document.createElement("span");
  span.textContent = libelle;
  div.append(b, span);
  return div;
}

async function demarrer() {
  document.querySelectorAll(".pied .contact").forEach((a) => { a.href = lienContact(); });
  try {
    const donnees = await charger();
    const vivants = [...etat.personnes.values()].filter((p) => !p.inconnu);
    const familles = vivants.filter((p) => p.parrain == null).length;
    const annees = Object.keys(etat.promos).map(Number);
    const nf = (x) => x.toLocaleString("fr-FR");
    $("#stats").replaceChildren(
      tuile("t1", nf(vivants.length), "étudiant·es"),
      tuile("t2", nf(familles), "familles"),
      tuile("t3", annees.length, `promos, ${Math.min(...annees)} → ${Math.max(...annees)}`),
    );
    $("#maj").textContent = `Dernière mise à jour : ${new Date(donnees.genere_le).toLocaleDateString("fr-FR")}.`;
  } catch (e) {
    const p = document.createElement("p");
    p.className = "erreur";
    p.textContent = "Impossible de charger les données. Réessaie plus tard.";
    $("#stats").replaceChildren(p);
    console.error(e);
    return;
  }
  initRecherche($("#recherche"), $("#resultats"));
  initRecherche($("#recherche-accueil"), $("#resultats-accueil"));
  initMinicarte();
  window.addEventListener("hashchange", lireHash);
  // Rotation du téléphone, fenêtre redimensionnée : on replace l'arbre.
  let attente;
  window.addEventListener("resize", () => {
    clearTimeout(attente);
    attente = setTimeout(() => { if (etat.focus && !$("#vue").hidden) placerAuDepart(); }, 200);
  });
  lireHash();
}

demarrer();
