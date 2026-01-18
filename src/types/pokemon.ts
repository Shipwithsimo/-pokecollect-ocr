export interface PokemonCard {
  id: string;
  card_id: string;
  name: string;
  set_name: string;
  set_code: string;
  card_number: string;
  rarity: string;
  card_type: "Pokemon" | "Trainer" | "Energy";
  pokemon_type?: string;
  hp?: number;
  image_url: string;
  market_price_eur?: number;
  market_price_usd?: number;
}

export interface UserCard {
  id: string;
  user_id: string;
  card_id: string;
  quantity: number;
  condition: "Mint" | "Near Mint" | "Excellent" | "Good" | "Played" | "Poor";
  notes?: string;
  user_image_url?: string;
  created_at: string;
  card?: PokemonCard;
}

export interface CollectionStats {
  total_cards: number;
  unique_cards: number;
  duplicates: number;
  total_value_eur: number;
}

export interface ScanCandidate {
  card_id: string;
  name: string;
  set_name: string;
  set_code: string;
  card_number: string;
  rarity: string;
  confidence: number;
  price_eur?: number;
  is_duplicate?: boolean;
  image_url?: string;
}

export interface ScanResult {
  candidates: ScanCandidate[];
  raw?: {
    name?: string;
    card_number?: string;
    set_name?: string;
    set_code?: string;
    rarity?: string;
    language?: string;
  };
  error?: string;
}
