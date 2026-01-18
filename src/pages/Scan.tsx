import { useState, useRef, useEffect } from "react";
import { Camera, Upload, ArrowLeft, Lightbulb, Check, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { ScanCandidate, ScanResult } from "@/types/pokemon";
import { collectionKeys } from "@/data/queries";
import { scanCardImage } from "@/lib/ocr-api";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { useSession } from "@/hooks/use-session";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

type ScanStep = "upload" | "preview" | "analyzing" | "results";

export default function Scan() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { session } = useSession();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<ScanStep>("upload");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [scanResults, setScanResults] = useState<ScanCandidate[]>([]);
  const [selectedCards, setSelectedCards] = useState<Set<number>>(new Set());
  const [isSaving, setIsSaving] = useState(false);
  const [isScanning, setIsScanning] = useState(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setSelectedFile(file);
      setPreviewUrl((prevUrl) => {
        if (prevUrl) {
          URL.revokeObjectURL(prevUrl);
        }
        return url;
      });
      setStep("preview");
    } else {
      setSelectedFile(null);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      toast.error("Carica un'immagine prima di analizzare.");
      return;
    }

    setStep("analyzing");
    setProgress(0);
    setIsScanning(true);

    try {
      const result = (await scanCardImage(selectedFile)) as ScanResult;
      const candidates = result.candidates ?? [];
      setScanResults(candidates);
      if (result.error === "ocr_failed" || candidates.length === 0) {
        toast.error("Carta non trovata. Prova con una foto piu' nitida.");
        setSelectedCards(new Set());
      } else {
        setSelectedCards(new Set([0]));
      }
      setStep("results");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Errore di scansione";
      toast.error(message);
      setStep("preview");
    } finally {
      setIsScanning(false);
      setProgress(100);
    }
  };

  useEffect(() => {
    if (step === "analyzing" && isScanning) {
      const interval = setInterval(() => {
        setProgress((prev) => Math.min(prev + 10, 90));
      }, 500);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [step, isScanning]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const toggleCard = (index: number) => {
    const newSet = new Set(selectedCards);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setSelectedCards(newSet);
  };

  const handleAddToCollection = async () => {
    if (!session) {
      toast.error("Accedi per salvare la collezione.");
      return;
    }

    setIsSaving(true);

    try {
      const userId = session.user.id;
      const entries = Array.from(selectedCards)
        .map((index) => scanResults[index])
        .filter((card) => card?.card_id);

      if (entries.length === 0) {
        toast.error("Nessuna carta selezionata.");
        return;
      }

      for (const card of entries) {
        const { data: existing } = await supabase
          .from("user_cards")
          .select("id, quantity")
          .eq("user_id", userId)
          .eq("card_id", card.card_id)
          .maybeSingle();

        if (existing) {
          await supabase
            .from("user_cards")
            .update({ quantity: existing.quantity + 1 })
            .eq("id", existing.id);
        } else {
          await supabase.from("user_cards").insert({
            user_id: userId,
            card_id: card.card_id,
            quantity: 1,
            condition: "Near Mint",
          });
        }
      }

      await queryClient.invalidateQueries({ queryKey: collectionKeys.all });
      await queryClient.invalidateQueries({ queryKey: collectionKeys.stats() });
      toast.success(`${entries.length} carte aggiunte alla collezione!`);
      navigate("/collection");
    } catch (error) {
      toast.error("Errore durante il salvataggio.");
    } finally {
      setIsSaving(false);
      setSelectedCards(new Set());
    }
  };

  const totalValue = Array.from(selectedCards).reduce(
    (sum, idx) => sum + (scanResults[idx]?.price_eur || 0),
    0
  );

  const resetScan = () => {
    setStep("upload");
    setPreviewUrl((prevUrl) => {
      if (prevUrl) {
        URL.revokeObjectURL(prevUrl);
      }
      return null;
    });
    setProgress(0);
    setScanResults([]);
    setSelectedCards(new Set());
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <AppLayout showNav={step === "upload"}>
      <div className="min-h-screen px-5 pt-12 pb-6">
        {/* Upload Step */}
        {step === "upload" && (
          <div className="space-y-6 animate-fade-in">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-foreground mb-2">
                Scansiona le tue carte
              </h1>
              <p className="text-muted-foreground">
                Fotografa una carta o un foglio intero
              </p>
            </div>

            <div className="space-y-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileSelect}
                className="hidden"
              />
              
              <Button
                onClick={() => {
                  if (fileInputRef.current) {
                    fileInputRef.current.setAttribute("capture", "environment");
                    fileInputRef.current.click();
                  }
                }}
                variant="hero"
                size="xl"
                className="w-full"
              >
                <Camera className="w-5 h-5" />
                Scatta Foto
              </Button>
              
              <Button
                onClick={() => {
                  if (fileInputRef.current) {
                    fileInputRef.current.removeAttribute("capture");
                    fileInputRef.current.click();
                  }
                }}
                variant="outline"
                size="xl"
                className="w-full"
              >
                <Upload className="w-5 h-5" />
                Carica Immagine
              </Button>
            </div>

            <div className="bg-accent rounded-2xl p-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <Lightbulb className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <p className="font-medium text-foreground text-sm mb-1">
                    Suggerimenti per risultati migliori
                  </p>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>• Buona illuminazione, evita ombre</li>
                    <li>• Inquadra bene la carta o il foglio</li>
                    <li>• Evita riflessi sulla carta</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Preview Step */}
        {step === "preview" && previewUrl && (
          <div className="space-y-6 animate-fade-in">
            <button onClick={resetScan} className="flex items-center gap-2 text-muted-foreground">
              <ArrowLeft className="w-4 h-4" />
              Indietro
            </button>

            <div className="rounded-2xl overflow-hidden shadow-card">
              <img
                src={previewUrl}
                alt="Preview"
                className="w-full object-contain max-h-[50vh]"
              />
            </div>

            <div className="flex gap-3">
              <Button
                onClick={resetScan}
                variant="outline"
                size="lg"
                className="flex-1"
                aria-label="Annulla scansione"
              >
                <X className="w-4 h-4" />
                Annulla
              </Button>
              <Button
                onClick={handleAnalyze}
                variant="hero"
                size="lg"
                className="flex-1"
                aria-label="Analizza immagine"
                disabled={isScanning}
              >
                {isScanning ? "Analisi..." : "🔍 Analizza"}
              </Button>
            </div>
          </div>
        )}

        {/* Analyzing Step */}
        {step === "analyzing" && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 animate-fade-in">
            <div className="w-20 h-20 rounded-full gradient-hero flex items-center justify-center animate-pulse">
              <Camera className="w-10 h-10 text-primary-foreground" />
            </div>
            <div className="text-center">
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Sto analizzando l'immagine...
              </h2>
              <p className="text-muted-foreground">
                Identificazione carte in corso
              </p>
            </div>
            <div className="w-full max-w-xs">
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full gradient-hero transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-center text-sm text-muted-foreground mt-2">
                {progress}%
              </p>
            </div>
          </div>
        )}

        {/* Results Step */}
        {step === "results" && (
          <div className="space-y-4 animate-fade-in pb-24">
            <div className="flex items-center justify-between">
              <button
                onClick={resetScan}
                className="flex items-center gap-2 text-muted-foreground"
                aria-label="Avvia nuova scansione"
              >
                <ArrowLeft className="w-4 h-4" />
                Nuova scansione
              </button>
              <h1 className="text-lg font-semibold">
                Carte Trovate ({isScanning ? "..." : scanResults.length})
              </h1>
            </div>

            <div className="space-y-3">
              {scanResults.length === 0 ? (
                <div className="rounded-2xl bg-card p-6 text-center shadow-card">
                  <p className="text-muted-foreground">Nessun risultato trovato.</p>
                </div>
              ) : (
                scanResults.map((card, index) => (
                  <div
                    key={index}
                    className={cn(
                      "flex gap-4 p-3 rounded-2xl bg-card shadow-card transition-all",
                      selectedCards.has(index) && "ring-2 ring-primary"
                    )}
                  >
                    <button
                      onClick={() => toggleCard(index)}
                      className="shrink-0"
                      aria-label={`Seleziona ${card.name}`}
                      disabled={!card.card_id}
                    >
                      <Checkbox checked={selectedCards.has(index)} disabled={!card.card_id} />
                    </button>
                    
                    <div className="w-16 h-22 rounded-lg overflow-hidden bg-muted shrink-0">
                      {card.image_url ? (
                        <img
                          src={card.image_url}
                          alt={card.name}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full bg-muted" />
                      )}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-semibold text-foreground truncate">
                          {card.name || "Carta non trovata"}
                        </h3>
                        {card.price_eur ? (
                          <span className="text-primary font-semibold shrink-0">
                            €{card.price_eur.toFixed(2)}
                          </span>
                        ) : null}
                      </div>
                      <p className="text-sm text-muted-foreground truncate">
                        {card.set_name || "Dati non disponibili"}
                        {card.card_number ? ` • ${card.card_number}` : ""}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        {!card.card_id ? (
                          <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-600 text-xs font-medium">
                            NON TROVATA
                          </span>
                        ) : card.is_duplicate ? (
                          <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-600 text-xs font-medium">
                            DOPPIONE
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-600 text-xs font-medium">
                            NUOVA
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {card.confidence}% sicuro
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Fixed Footer */}
            <div className="fixed bottom-0 left-0 right-0 bg-card border-t border-border p-4 safe-bottom">
              <div className="flex items-center justify-between mb-3 max-w-lg mx-auto">
                <span className="text-sm text-muted-foreground">
                  {selectedCards.size} carte selezionate
                </span>
                <span className="font-semibold text-primary">
                  €{totalValue.toFixed(2)}
                </span>
              </div>
              <Button
                onClick={handleAddToCollection}
                variant="hero"
                size="lg"
                className="w-full max-w-lg mx-auto"
                disabled={selectedCards.size === 0 || isSaving || isScanning}
              >
                <Check className="w-4 h-4" />
                {isSaving ? "Salvataggio..." : "Aggiungi alla Collezione"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
