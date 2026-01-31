export interface Word {
  name: string;
  slug: string;
  category: string;
  emoji: string;
  description: string;
}

export const words: Word[] = [
  // Cibo
  { name: "Albicocca", slug: "Albicocca", category: "Cibo", emoji: "🍑", description: "Il frutto estivo dolce e profumato" },
  { name: "Briciole", slug: "Briciole", category: "Cibo", emoji: "🍞", description: "I piccoli frammenti del pane" },
  { name: "Pop Corn", slug: "Pop Corn", category: "Cibo", emoji: "🍿", description: "Il mais scoppiato amato al cinema" },
  { name: "Cotechino grigliato", slug: "cotechino grigliato", category: "Cibo", emoji: "🌭", description: "L'insaccato cotto alla griglia" },
  { name: "Maiale", slug: "maiale", category: "Cibo", emoji: "🐷", description: "L'animale da cui viene il salame" },

  // Mestieri
  { name: "Panettiere", slug: "Panettiere", category: "Mestieri", emoji: "🥖", description: "Chi fa il pane ogni mattina" },
  { name: "Macellaio", slug: "Macellaio", category: "Mestieri", emoji: "🥩", description: "Chi vende la carne" },
  { name: "Pettegola", slug: "Pettegola", category: "Mestieri", emoji: "🗣️", description: "Chi parla troppo degli altri" },

  // Oggetti
  { name: "Roncola", slug: "Roncola", category: "Oggetti", emoji: "🔪", description: "L'attrezzo per tagliare i rami" },
  { name: "Coperchio", slug: "coperchio", category: "Oggetti", emoji: "🫕", description: "Ciò che chiude pentole e barattoli" },
  { name: "Imbuto", slug: "Imbuto", category: "Oggetti", emoji: "📐", description: "Per versare liquidi senza sporcare" },
  { name: "Grembiule", slug: "grembiule", category: "Oggetti", emoji: "👗", description: "Si indossa per cucinare" },
  { name: "Ciabatta", slug: "ciabatta", category: "Oggetti", emoji: "🩴", description: "La calzatura comoda da casa" },
  { name: "Orologio", slug: "orologio", category: "Oggetti", emoji: "⌚", description: "Segna il passare del tempo" },
  { name: "Tasca", slug: "tasca", category: "Oggetti", emoji: "👖", description: "Dove si tengono le chiavi" },
  { name: "Fiammifero", slug: "Fiammifero", category: "Oggetti", emoji: "🔥", description: "Per accendere il fuoco" },

  // Animali e Natura
  { name: "Libellula", slug: "Libellula", category: "Natura", emoji: "🪰", description: "L'insetto elegante vicino all'acqua" },
  { name: "Gallina", slug: "Gallina", category: "Natura", emoji: "🐔", description: "L'animale che fa le uova" },
  { name: "Talpa", slug: "talpa", category: "Natura", emoji: "🐀", description: "L'animale che scava sottoterra" },
  { name: "Ragnatela", slug: "ragnatela", category: "Natura", emoji: "🕸️", description: "La casa del ragno" },
  { name: "Sasso", slug: "Sasso", category: "Natura", emoji: "🪨", description: "La pietra che si trova ovunque" },

  // Corpo
  { name: "Ombelico", slug: "Ombelico", category: "Corpo", emoji: "👶", description: "Il segno della nascita" },

  // Stati
  { name: "Bagnato", slug: "Bagnato", category: "Stati", emoji: "💧", description: "Quando qualcosa è umido" },
  { name: "Fradicio", slug: "Fradicio", category: "Stati", emoji: "🌧️", description: "Completamente bagnato" },
  { name: "Scapolo", slug: "Scapolo", category: "Stati", emoji: "💍", description: "Chi non è ancora sposato" },

  // Carte da gioco
  { name: "L'Asso di Ori", slug: "l'Asso di Ori", category: "Carte", emoji: "💰", description: "La carta più preziosa" },
  { name: "L'Asso di Spade", slug: "l'Asso di Spade", category: "Carte", emoji: "⚔️", description: "La carta del combattimento" },
  { name: "L'Asso di Bastoni", slug: "l'Asso di Bastoni", category: "Carte", emoji: "🏑", description: "La carta della forza" },
  { name: "L'Asso di Coppe", slug: "l'Asso di Coppe", category: "Carte", emoji: "🏆", description: "La carta della vittoria" },
];

export const categories = [...new Set(words.map(w => w.category))];

export function getWordBySlug(slug: string): Word | undefined {
  return words.find(w => w.slug.toLowerCase() === slug.toLowerCase());
}

export function getWordsByCategory(category: string): Word[] {
  return words.filter(w => w.category === category);
}
