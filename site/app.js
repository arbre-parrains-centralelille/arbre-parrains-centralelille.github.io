"use strict";

// Adresse affichée pour les corrections et les demandes de retrait.
const CONTACT = "arbre.parrains.centralelille@gmail.com";

// Dimensions de l'arbre (en pixels SVG)
const NOEUD_L = 136, NOEUD_H = 46, ECART_X = 14, RANGEE = 96, MARGE_BANDE = 150;

const $ = (sel) => document.querySelector(sel);
const etat = { personnes: new Map(), fillots: new Map(), promos: {}, zoom: null, focus: null };

// --- Données ----------------------------------------------------------------

function normaliser(s) {
  return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[-–—'’._]/g, " ").trim();
}

function nomComplet(p) {
  return p.inconnu ? "Inconnu·e" : [p.prenom, p.nom].filter(Boolean).join(" ");
}

function libellePromo(promo) {
  const nom = etat.promos[promo];
  return nom ? `Promo ${promo} · ${nom}` : `Promo ${promo}`;
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

function initRecherche() {
  const champ = $("#recherche"), liste = $("#resultats");
  let items = [], actif = -1;

  const fermer = () => { liste.hidden = true; champ.setAttribute("aria-expanded", "false"); actif = -1; };
  const choisir = (p) => { fermer(); champ.value = ""; champ.blur(); allerA(p.id); };
  const surligner = () => [...liste.children].forEach((li, i) => li.setAttribute("aria-selected", i === actif));

  champ.addEventListener("input", () => {
    items = rechercher(champ.value);
    liste.replaceChildren();
    if (!champ.value.trim()) return fermer();
    if (!items.length) {
      liste.innerHTML = '<li class="vide">Aucun résultat</li>';
    }
    items.forEach((p, i) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.innerHTML = `<strong></strong><br><small></small>`;
      li.querySelector("strong").textContent = nomComplet(p);
      li.querySelector("small").textContent = libellePromo(p.promo);
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
  if (p) afficher(p);
  else document.title = "Arbre des parrains · Centrale Lille";
}

// --- Fiche ------------------------------------------------------------------------

// Les liens (parrain, fillots…) sont déjà visibles dans l'arbre : la fiche est
// réservée aux informations propres à la personne (formation, associations… à venir).
function remplirFiche(p, racine, taille, generations) {
  const fiche = $("#fiche");
  fiche.replaceChildren();
  const h2 = document.createElement("h2");
  h2.textContent = nomComplet(p);
  const promo = document.createElement("p");
  promo.className = "promo";
  promo.textContent = libellePromo(p.promo);
  fiche.append(h2, promo);

  const fam = document.createElement("p");
  fam.className = "famille";
  fam.textContent = `Famille de ${taille} personnes sur ${generations} générations, depuis ${nomComplet(racine)} (${racine.promo}).`;
  fiche.appendChild(fam);
}

// --- Arbre ------------------------------------------------------------------------

function tronquer(s, max = 17) {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function afficher(p) {
  etat.focus = p;
  document.title = `${nomComplet(p)} · Arbre des parrains`;

  const lignee = ancetres(p);
  const racine = lignee.length ? lignee[lignee.length - 1] : p;
  const lignee_ids = new Set([p.id, ...lignee.map((a) => a.id), ...descendants(p).map((d) => d.id)]);
  const parrain = parrainDe(p);
  const fratrie_ids = new Set(parrain ? etat.fillots.get(parrain.id).map((f) => f.id) : []);

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
  const minX = d3.min(noeuds, (d) => d.x) - NOEUD_L / 2, maxX = d3.max(noeuds, (d) => d.x) + NOEUD_L / 2;
  remplirFiche(p, racine, noeuds.length, promos.length);

  const svg = d3.select("#arbre");
  svg.selectAll("*").remove();
  const g = svg.append("g");

  // Bandes de promo
  const bandes = g.append("g").selectAll("g").data(d3.range(promos[0], promos[promos.length - 1] + 1)).join("g")
    .attr("class", "bande");
  bandes.filter((_, i) => i % 2 === 0).append("rect")
    .attr("x", minX - MARGE_BANDE).attr("y", (pr) => (pr - racine.promo) * RANGEE - RANGEE / 2)
    .attr("width", maxX - minX + MARGE_BANDE + 40).attr("height", RANGEE);
  bandes.append("text")
    .attr("x", minX - MARGE_BANDE + 10).attr("y", (pr) => (pr - racine.promo) * RANGEE - 4)
    .text((pr) => pr);
  bandes.append("text")
    .attr("x", minX - MARGE_BANDE + 10).attr("y", (pr) => (pr - racine.promo) * RANGEE + 12)
    .style("font-weight", 400).text((pr) => tronquer(etat.promos[pr] || "", 18));

  // Liens parrain -> fillot (coudés). Un lien qui traverse un fantôme est découpé en
  // segments qui passent par son centre.
  const idFinal = (data) => { while (data.fantome) data = data.suite; return data.id; };
  g.append("g").selectAll("path").data(h.links()).join("path")
    .attr("class", (l) => "lien" +
      (lignee_ids.has(reel(l.source).data.id) && lignee_ids.has(idFinal(l.target.data)) ? " lignee" : ""))
    .attr("d", (l) => {
      const y1 = l.source.y + (l.source.data.fantome ? 0 : NOEUD_H / 2);
      const y2 = l.target.y - (l.target.data.fantome ? 0 : NOEUD_H / 2);
      const ym = l.source.y + RANGEE / 2;
      return `M${l.source.x},${y1}V${ym}H${l.target.x}V${y2}`;
    });

  // Nœuds
  const n = g.append("g").selectAll("g").data(noeuds).join("g")
    .attr("class", (d) => {
      const id = d.data.id;
      const role = id === p.id ? "focus" : lignee_ids.has(id) ? "lignee" : fratrie_ids.has(id) ? "fratrie" : "autre";
      return `noeud ${role}` + (d.data.inconnu ? " inconnu" : "");
    })
    .attr("transform", (d) => `translate(${d.x - NOEUD_L / 2},${d.y - NOEUD_H / 2})`)
    .attr("tabindex", 0)
    .on("click", (_, d) => allerA(d.data.id))
    .on("keydown", (e, d) => { if (e.key === "Enter") allerA(d.data.id); });
  n.append("title").text((d) => `${nomComplet(d.data)} — ${libellePromo(d.data.promo)}`);
  n.append("rect").attr("width", NOEUD_L).attr("height", NOEUD_H).attr("rx", 3);
  n.append("text").attr("class", "prenom").attr("x", NOEUD_L / 2).attr("y", 19).attr("text-anchor", "middle")
    .text((d) => tronquer(d.data.inconnu ? "?" : d.data.prenom || ""));
  n.append("text").attr("x", NOEUD_L / 2).attr("y", 35).attr("text-anchor", "middle")
    .text((d) => tronquer(d.data.inconnu ? "Inconnu·e" : d.data.nom || ""));

  // Zoom et déplacement (souris, molette, doigts)
  etat.zoom = d3.zoom().scaleExtent([0.15, 2.5]).on("zoom", (e) => g.attr("transform", e.transform));
  svg.call(etat.zoom).on("dblclick.zoom", null);
  etat.boite = { x: minX - MARGE_BANDE, y: -RANGEE / 2, l: maxX - minX + MARGE_BANDE + 40, h: promos.length ? (promos[promos.length - 1] - racine.promo + 1) * RANGEE : RANGEE };
  etat.noeudFocus = noeuds.find((d) => d.data.id === p.id);

  // Si toute la famille tient lisiblement à l'écran, on la montre en entier ;
  // sinon on centre sur la personne cherchée.
  const { width, height } = svg.node().getBoundingClientRect();
  const echelleEnsemble = Math.min(width / etat.boite.l, height / etat.boite.h);
  if (echelleEnsemble >= 0.7) vueEnsemble(false); else centrer(false);
}

function centrer(anime = true) {
  const svg = d3.select("#arbre");
  const { width, height } = svg.node().getBoundingClientRect();
  const k = width < 600 ? 0.8 : 1;
  const d = etat.noeudFocus, b = etat.boite, marge = 16;
  // Centré sur la personne, mais sans laisser de vide au-dessus ou en dessous de l'arbre.
  let ty = height / 2 - d.y * k;
  if (b.h * k + 2 * marge > height) {
    ty = Math.min(ty, marge - b.y * k);
    ty = Math.max(ty, height - marge - (b.y + b.h) * k);
  } else {
    ty = (height - b.h * k) / 2 - b.y * k;
  }
  const t = d3.zoomIdentity.translate(width / 2 - d.x * k, ty).scale(k);
  (anime ? svg.transition().duration(400) : svg).call(etat.zoom.transform, t);
}

function vueEnsemble(anime = true) {
  const svg = d3.select("#arbre");
  const { width, height } = svg.node().getBoundingClientRect();
  const b = etat.boite;
  const k = Math.min(1.1, 0.95 * Math.min(width / b.l, height / b.h));
  const t = d3.zoomIdentity
    .translate(width / 2 - (b.x + b.l / 2) * k, height / 2 - (b.y + b.h / 2) * k).scale(k);
  (anime ? svg.transition().duration(400) : svg).call(etat.zoom.transform, t);
}

// --- Démarrage ----------------------------------------------------------------------

async function demarrer() {
  const contact = $("#contact");
  contact.href = `mailto:${CONTACT}?subject=${encodeURIComponent("Arbre des parrains")}`;
  try {
    const donnees = await charger();
    const vivants = [...etat.personnes.values()].filter((p) => !p.inconnu);
    const familles = vivants.filter((p) => p.parrain == null).length;
    const annees = Object.keys(etat.promos).map(Number);
    $("#stats").innerHTML =
      `<b>${vivants.length}</b> étudiants · <b>${familles}</b> familles · promos <b>${Math.min(...annees)}</b> à <b>${Math.max(...annees)}</b>`;
    $("#maj").textContent = `Dernière mise à jour : ${new Date(donnees.genere_le).toLocaleDateString("fr-FR")}.`;
  } catch (e) {
    $("#stats").textContent = "Impossible de charger les données. Réessaie plus tard.";
    console.error(e);
    return;
  }
  initRecherche();
  $("#btn-centrer").addEventListener("click", () => centrer());
  $("#btn-ensemble").addEventListener("click", () => vueEnsemble());
  window.addEventListener("hashchange", lireHash);
  lireHash();
}

demarrer();
