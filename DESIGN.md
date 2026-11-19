# Design du site

Repères pour modifier l'apparence sans casser ce qui a été décidé (refonte de novembre 2026).
Les maquettes sont sur le canevas Claude « Arbre des parrains · refonte mobile ».

## Principes

- **Téléphone d'abord** : le site sert surtout à se retrouver et à montrer sa famille depuis un téléphone.
- **Un vrai arbre partout**, le même sur ordinateur et sur téléphone : on zoome (molette, pincement) et on se
  déplace (glisser). Pas de bouton « Centrer » ni « Vue d'ensemble ».
- **L'arbre est toujours entier** : aucune branche n'est repliée.

## Charte

Charte Centrale Lille (oct. 2022), interprétée sur un ton BDE.

| Rôle | Valeur |
|---|---|
| Ardoise (en-tête, lignée) | `#376795` |
| Jaune d'or (personne choisie, ombre décalée) | `#f9b000` |
| Jaune soleil (filet sous l'en-tête) | `#ffcc00` |
| Co-fillot·e | fond `#ffeea6`, bord `#c98d00` |
| Encre (texte, contours forts) | `#1d2f42` |
| Police | Roboto (hébergée dans `site/vendor/`, rien n'est chargé depuis un serveur tiers) ; titres en 900 |
| Formes | carrés à coins de 4 px, polygone à 10 côtés (logo, badge), sinusoïde (accueil) |

## L'arbre

- Une rangée par promo ; à gauche, l'année en grand et le nom de promo.
- Cases de 92 × 46 px (la personne choisie : 104 × 54 px, jaune, contour encre et ombre décalée).
- Liens coudés aux angles arrondis ; la lignée de la personne choisie (ancêtres et descendants) en trait ardoise épais.
- Fond quadrillé de points.

## La carte de la personne

Elle est **attachée à l'écran, jamais à l'arbre** :

- ordinateur : en haut à gauche ;
- téléphone (< 700 px) : bandeau compact en bas de l'écran.

À l'ouverture (`placerAuDepart` dans `app.js`), on cherche le plus grand zoom (≤ 1) qui montre tout l'arbre
sans qu'aucune case passe sous la carte : dans tout l'écran, à droite de la carte ou en dessous. Si l'arbre est trop
grand pour rester lisible, on zoome sur la personne choisie, placée dans la zone libre. Ensuite, quand on se
déplace, l'arbre passe sous la carte.

## La mini-carte

En haut à droite, elle reprend la forme de l'arbre et encadre la partie affichée. Elle n'apparaît que si l'arbre
dépasse de l'écran. La toucher recentre l'arbre sur l'endroit touché.
