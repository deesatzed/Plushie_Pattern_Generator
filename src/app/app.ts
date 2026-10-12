import { ChangeDetectionStrategy, Component, signal, computed } from '@angular/core';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';

export interface ProjectPiece {
  id: string;
  name: string;
  shapeType: 'circle' | 'rect' | 'oval' | 'triangle' | 'shield';
  color: string;
  count: number;
  label: string;
  width: number;
  height: number;
  x: number;
  y: number;
  rotation: number;
  scale: number;
}

export interface FabricRequirement {
  fabricName: string;
  amountRequired: string;
  color: string;
  textureRecommendation: string;
}

export interface CustomizationConfig {
  optionId: string;
  optionTitle: string;
  selectionType: 'select' | 'boolean';
  choices: string[];
  defaultValue: string;
  description: string;
}

export interface SewingGuide {
  sewingMachineSettings: {
    tension: string;
    stitchType: string;
    needleType: string;
  };
  materialsList: string[];
  preparationSteps: string[];
  stitchingSteps: string[];
  finishingSteps: string[];
  tailoringProTips: string[];
}

export interface PlushieProject {
  id: string;
  title: string;
  createdAt: string;
  imageUrls: string[]; 
  selectedIndexes: number[];
  difficulty: 'Novice' | 'Scout' | 'Artisan' | '';
  difficultyReasoning?: string;
  sewingMachineVsHand?: string;
  estimatedTime?: string;
  requiredFabrics?: FabricRequirement[];
  cuttingPieces?: ProjectPiece[];
  customizations?: Record<string, string>;
  customizationOptions?: CustomizationConfig[];
  refinementPrompt?: string;
  outcomePreviewUrl?: string;
  buildGuide?: SewingGuide;
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-root',
  imports: [CommonModule, ReactiveFormsModule, FormsModule, MatIconModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  // Authentication & Session signals
  profileName = signal<string>('');
  profileLevel = signal<string>('Novice');
  isAuthed = signal<boolean>(false);
  loginNameInput = signal<string>('');

  // Navigation desk signals
  currentStep = signal<'auth' | 'desk' | 'image-gather' | 'complexity' | 'preview' | 'guide'>('auth');
  savedProjects = signal<PlushieProject[]>([]);
  activeProject = signal<PlushieProject | null>(null);

  // Idea generation engine
  ideaPrompt = signal<string>('');
  isGeneratingIdea = signal<boolean>(false);
  ideaMessage = signal<string>('');

  // Analysis signals
  isAnalyzing = signal<boolean>(false);
  activePieceId = signal<string | null>(null);

  // Preview & guide compilation
  isGeneratingPreview = signal<boolean>(false);
  extraRefinementPrompt = signal<string>('');
  isGeneratingGuide = signal<boolean>(false);
  isPrintMode = signal<boolean>(false);

  // Label toggling and grid snapping controls
  showLabels = signal<boolean>(true);
  snapToGrid = signal<boolean>(false);
  showSeamAllowance = signal<boolean>(true);
  seamAllowanceSize = signal<number>(8);

  togglePrintMode() {
    this.isPrintMode.update(val => !val);
  }

  triggerPrint() {
    if (typeof window !== 'undefined') {
      window.print();
    }
  }

  // Customization selection store
  customizationValues = signal<Record<string, string>>({});

  hasCustomizations = computed(() => {
    const vals = this.customizationValues();
    return vals && Object.keys(vals).length > 0;
  });

  // Quick prompt presets
  presets = [
    { label: 'Marshmallow Pink Lamb', prompt: 'Chubby round marshmallow-pink sheep with little spiral wool ears' },
    { label: 'Mallow Blue Dragon', prompt: 'Squishy soft baby blue dragon with tiny rounded wings and sleepy eyes' },
    { label: 'Forest Teddy Bear', prompt: 'Friendly running-stitch woodland teddy bear doll made of textured linen' },
    { label: 'Pastel Baby Dino', prompt: 'Chubby cute pastel green triceratops plush with soft fleece horns' }
  ];

  // Selected piece helper for virtual fabric tailor board
  selectedPiece = computed(() => {
    const proj = this.activeProject();
    const id = this.activePieceId();
    if (!proj || !id || !proj.cuttingPieces) return null;
    return proj.cuttingPieces.find(p => p.id === id) || null;
  });

  constructor() {
    // Synchronize local session storage
    if (typeof window !== 'undefined') {
      const storedName = localStorage.getItem('plushie_profile_name');
      const storedLevel = localStorage.getItem('plushie_profile_level');
      if (storedName) {
        this.profileName.set(storedName);
        this.profileLevel.set(storedLevel || 'Novice');
        this.isAuthed.set(true);
        this.currentStep.set('desk');
      }
      this.loadSavedProjects();
    }
  }

  // Auth Operations
  login(name: string, level: string) {
    if (!name.trim()) return;
    this.profileName.set(name);
    this.profileLevel.set(level);
    this.isAuthed.set(true);
    if (typeof window !== 'undefined') {
      localStorage.setItem('plushie_profile_name', name);
      localStorage.setItem('plushie_profile_level', level);
    }
    this.currentStep.set('desk');
  }

  logout() {
    this.profileName.set('');
    this.profileLevel.set('Novice');
    this.isAuthed.set(false);
    this.activeProject.set(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('plushie_profile_name');
      localStorage.removeItem('plushie_profile_level');
    }
    this.currentStep.set('auth');
  }

  // Project Database management
  loadSavedProjects() {
    if (typeof window !== 'undefined') {
      const db = localStorage.getItem('plushie_patterns_pool');
      if (db) {
        try {
          this.savedProjects.set(JSON.parse(db));
        } catch (e) {
          console.error('Failed parsing patterns pool from local disk:', e);
        }
      }
    }
  }

  saveActiveProjectToDisk() {
    const proj = this.activeProject();
    if (!proj) return;
    
    const currentPool = [...this.savedProjects()];
    const index = currentPool.findIndex(p => p.id === proj.id);
    if (index !== -1) {
      currentPool[index] = proj;
    } else {
      currentPool.unshift(proj);
    }
    this.savedProjects.set(currentPool);
    if (typeof window !== 'undefined') {
      localStorage.setItem('plushie_patterns_pool', JSON.stringify(currentPool));
    }
  }

  deleteProject(projectId: string, event: Event) {
    event.stopPropagation();
    const currentPool = this.savedProjects().filter(p => p.id !== projectId);
    this.savedProjects.set(currentPool);
    if (typeof window !== 'undefined') {
      localStorage.setItem('plushie_patterns_pool', JSON.stringify(currentPool));
    }
    if (this.activeProject()?.id === projectId) {
      this.activeProject.set(null);
    }
  }

  startNewProject() {
    const newProject: PlushieProject = {
      id: 'plush-' + Date.now(),
      title: 'Plushie Pattern Guide #' + (this.savedProjects().length + 1),
      createdAt: new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
      imageUrls: [],
      selectedIndexes: [],
      difficulty: '',
    };
    this.activeProject.set(newProject);
    this.customizationValues.set({});
    this.currentStep.set('image-gather');
  }

  resumeProject(proj: PlushieProject) {
    this.activeProject.set(proj);
    
    // restore customization values
    if (proj.customizations) {
      this.customizationValues.set(proj.customizations);
    } else {
      this.customizationValues.set({});
    }

    // Determine correct step to drop them in based on project progress
    if (proj.buildGuide) {
      this.currentStep.set('guide');
    } else if (proj.outcomePreviewUrl) {
      this.currentStep.set('preview');
    } else if (proj.difficulty) {
      this.currentStep.set('complexity');
    } else {
      this.currentStep.set('image-gather');
    }
  }

  // Step 1: Image gathering (Upload and Generate)
  onUserImagesSelected(event: Event) {
    const files = (event.target as HTMLInputElement).files;
    if (!files || files.length === 0) return;

    const filesList = Array.from(files);
    let loadedCount = 0;
    const base64s: string[] = [];

    for (const file of filesList) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const base64 = e.target?.result as string;
        if (base64) {
          base64s.push(base64);
        }
        loadedCount++;
        
        // Once all files are read, we perform a single state update to avoid races
        if (loadedCount === filesList.length) {
          const currentSelected = this.activeProject();
          if (currentSelected) {
            const startIndex = currentSelected.imageUrls.length;
            const newIndexes = base64s.map((_, i) => startIndex + i);
            const updated = {
              ...currentSelected,
              imageUrls: [...currentSelected.imageUrls, ...base64s],
              selectedIndexes: [...currentSelected.selectedIndexes, ...newIndexes].slice(-3) // auto-select, keeping up to 3
            };
            this.activeProject.set(updated);
            this.saveActiveProjectToDisk();
          }
        }
      };
      reader.readAsDataURL(file);
    }
  }

  async generateReferenceImage(promptText: string) {
    if (!promptText.trim()) return;
    this.isGeneratingIdea.set(true);
    this.ideaMessage.set('Spooling threads & generating plush design...');

    try {
      const response = await fetch('/api/generate-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptText })
      });
      const data = await response.json();
      
      if (data.success && data.url) {
        const currentSelected = this.activeProject();
        if (currentSelected) {
          const newIndex = currentSelected.imageUrls.length;
          const updated = {
            ...currentSelected,
            imageUrls: [...currentSelected.imageUrls, data.url],
            selectedIndexes: [...currentSelected.selectedIndexes, newIndex].slice(-3) // auto-select, keeping up to 3
          };
          this.activeProject.set(updated);
          this.saveActiveProjectToDisk();
          this.ideaPrompt.set('');
          this.ideaMessage.set('Sewing idea created and added to collection!');
        }
      } else {
        this.ideaMessage.set('Failed to generate design card suggestion.');
      }
    } catch (err) {
      console.error(err);
      this.ideaMessage.set('Network issue generating design reference.');
    } finally {
      this.isGeneratingIdea.set(false);
      setTimeout(() => this.ideaMessage.set(''), 4000);
    }
  }

  // Step 2: Selecting 2-3 images for analysis
  toggleImageSelection(index: number) {
    const current = this.activeProject();
    if (!current) return;

    const selected = [...current.selectedIndexes];
    const presentIndex = selected.indexOf(index);
    if (presentIndex !== -1) {
      // remove
      selected.splice(presentIndex, 1);
    } else {
      // add
      if (selected.length >= 3) {
        // limit 3
        selected.shift();
      }
      selected.push(index);
    }

    this.activeProject.set({
      ...current,
      selectedIndexes: selected
    });
    this.saveActiveProjectToDisk();
  }

  // Step 3: Send selected images for Pattern & Complexity Evaluation
  async evaluateComplexity() {
    const current = this.activeProject();
    if (!current || current.selectedIndexes.length === 0) return;

    this.isAnalyzing.set(true);
    
    // gather selected images
    const bases = current.selectedIndexes.map(idx => current.imageUrls[idx]);

    try {
      const response = await fetch('/api/analyze-complexity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          imagesBase64: bases
        })
      });

      if (!response.ok) {
        throw new Error('Analysis request failed on server');
      }

      const report = await response.json();
      
      // Map cuttingPieces coordinates and normalize sizes so they fit nicely
      const rawPieces = report.cuttingPieces || [];
      const paddedPieces: ProjectPiece[] = rawPieces.map((piece: Partial<ProjectPiece>, idx: number) => {
        let width = piece.width || 120;
        let height = piece.height || 100;
        
        // Cap dimensions to prevent massive board overlaps
        const maxDimension = 130;
        if (width > maxDimension || height > maxDimension) {
          const ratio = Math.min(maxDimension / width, maxDimension / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }
        
        // distribute cleanly in 4 columns
        const piecesPerRow = 4;
        const col = idx % piecesPerRow;
        const row = Math.floor(idx / piecesPerRow);
        
        return {
          id: piece.id || 'piece-' + idx,
          name: piece.name || 'Body panel',
          shapeType: piece.shapeType || 'rect',
          color: piece.color || '#CBD5E1',
          count: piece.count || 1,
          label: piece.label || piece.name || 'Cut Piece',
          width: width,
          height: height,
          x: 120 + col * 180,
          y: 90 + row * 150,
          rotation: 0,
          scale: 1.0
        };
      });

      // Default the customization choices
      const defaultCustomVals: Record<string, string> = {};
      if (report.customizationOptions) {
        report.customizationOptions.forEach((opt: CustomizationConfig) => {
          defaultCustomVals[opt.optionId] = opt.defaultValue;
        });
      }

      this.customizationValues.set(defaultCustomVals);

      const updatedProj: PlushieProject = {
        ...current,
        difficulty: report.difficulty,
        difficultyReasoning: report.difficultyReasoning,
        sewingMachineVsHand: report.sewingMachineVsHand,
        estimatedTime: report.estimatedTime,
        requiredFabrics: report.requiredFabrics,
        cuttingPieces: paddedPieces,
        customizations: defaultCustomVals,
        customizationOptions: report.customizationOptions,
        id: current.id // preserve
      };

      // update title based on characters if default
      if (current.title.startsWith('Plushie Pattern Guide #')) {
        updatedProj.title = `Fabric ${report.difficulty} Companion`;
      }

      this.activeProject.set(updatedProj);
      this.saveActiveProjectToDisk();
      
      // Auto transition
      this.currentStep.set('complexity');
    } catch (err) {
      console.error(err);
      alert('Seams analysis went askew! Keep coordinates clear and retry.');
    } finally {
      this.isAnalyzing.set(false);
    }
  }

  // Update customization drop list val
  updateCustomValue(id: string, value: string) {
    const vals = { ...this.customizationValues(), [id]: value };
    this.customizationValues.set(vals);
    const proj = this.activeProject();
    if (proj) {
      this.activeProject.set({
        ...proj,
        customizations: vals
      });
      this.saveActiveProjectToDisk();
    }
  }

  // Step 4: Outcome Mockup compilation
  async designOutcomePreview() {
    const current = this.activeProject();
    if (!current) return;

    this.isGeneratingPreview.set(true);

    try {
      const response = await fetch('/api/generate-plushie-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customizations: this.customizationValues(),
          refinementPrompt: this.extraRefinementPrompt()
        })
      });

      const data = await response.json();
      this.activeProject.set({
        ...current,
        outcomePreviewUrl: data.url
      });
      this.saveActiveProjectToDisk();
      this.currentStep.set('preview');
    } catch (err) {
      console.error(err);
      alert('Mockup design failed to compile visual.');
    } finally {
      this.isGeneratingPreview.set(false);
    }
  }

  // Drag and Drop canvas range slider manipulators
  updatePiecePos(axis: 'x' | 'y' | 'rotation' | 'scale', val: number) {
    const proj = this.activeProject();
    const activeId = this.activePieceId();
    if (!proj || !activeId || !proj.cuttingPieces) return;

    let finalVal = val;
    if (this.snapToGrid() && (axis === 'x' || axis === 'y')) {
      finalVal = Math.round(val / 20) * 20;
    }

    const updatedPieces = proj.cuttingPieces.map(piece => {
      if (piece.id === activeId) {
        return {
          ...piece,
          [axis]: finalVal
        };
      }
      return piece;
    });

    this.activeProject.set({
      ...proj,
      cuttingPieces: updatedPieces
    });
    this.saveActiveProjectToDisk();
  }

  fitPieceToGrid() {
    const proj = this.activeProject();
    const activeId = this.activePieceId();
    if (!proj || !activeId || !proj.cuttingPieces) return;

    const updatedPieces = proj.cuttingPieces.map(piece => {
      if (piece.id === activeId) {
        return {
          ...piece,
          x: Math.round(piece.x / 20) * 20,
          y: Math.round(piece.y / 20) * 20
        };
      }
      return piece;
    });

    this.activeProject.set({
      ...proj,
      cuttingPieces: updatedPieces
    });
    this.saveActiveProjectToDisk();
  }

  fitAllPiecesToGrid() {
    const proj = this.activeProject();
    if (!proj || !proj.cuttingPieces) return;

    const updatedPieces = proj.cuttingPieces.map(piece => {
      return {
        ...piece,
        x: Math.round(piece.x / 20) * 20,
        y: Math.round(piece.y / 20) * 20
      };
    });

    this.activeProject.set({
      ...proj,
      cuttingPieces: updatedPieces
    });
    this.saveActiveProjectToDisk();
  }

  // Safe Math/Geometry helpers for drawing Seam Allowance Inset boundaries in SVG
  getInsetCircleR(width: number): number {
    return Math.max(5, (width / 2) - this.seamAllowanceSize());
  }

  getInsetOvalRx(width: number): number {
    return Math.max(5, (width / 2) - this.seamAllowanceSize());
  }

  getInsetOvalRy(height: number): number {
    return Math.max(5, (height / 2) - this.seamAllowanceSize());
  }

  getInsetRectX(width: number): number {
    return -Math.max(5, (width / 2) - this.seamAllowanceSize());
  }

  getInsetRectY(height: number): number {
    return -Math.max(5, (height / 2) - this.seamAllowanceSize());
  }

  getInsetRectW(width: number): number {
    return Math.max(10, width - (this.seamAllowanceSize() * 2));
  }

  getInsetRectH(height: number): number {
    return Math.max(10, height - (this.seamAllowanceSize() * 2));
  }

  getInsetTrianglePoints(width: number, height: number): string {
    const size = this.seamAllowanceSize();
    const cy = height / 6;
    const factor = Math.max(0.1, 1 - (size * 2) / Math.min(width, height));
    
    const tY = cy + (-height / 2 - cy) * factor;
    const brX = (width / 2) * factor;
    const brY = cy + (height / 2 - cy) * factor;
    const blX = (-width / 2) * factor;
    const blY = cy + (height / 2 - cy) * factor;

    return `0,${tY} ${brX},${brY} ${blX},${blY}`;
  }

  getInsetShieldD(width: number, height: number): string {
    const size = this.seamAllowanceSize();
    const factor = Math.max(0.1, 1 - (size * 2) / Math.min(width, height));
    const hW = (width / 2) * factor;
    const hH = (height / 2) * factor;

    return `M 0 ${-hH} Q ${hW} ${-hH} ${hW} 0 Q ${hW} ${hH} 0 ${hH} Q ${-hW} ${hH} ${-hW} 0 Q ${-hW} ${-hH} 0 ${-hH}`;
  }

  selectPatternPiece(id: string) {
    this.activePieceId.set(id);
  }

  // Step 5: Submit Choices and Generate Thorough Instruction Sheets
  async compileBuildGuide() {
    const current = this.activeProject();
    if (!current) return;

    this.isGeneratingGuide.set(true);

    try {
      const response = await fetch('/api/generate-build-guide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          complexityResult: {
            difficulty: current.difficulty,
            requiredFabrics: current.requiredFabrics
          },
          customizations: this.customizationValues(),
          refinementPrompt: this.extraRefinementPrompt()
        })
      });

      const guide: SewingGuide = await response.json();
      
      this.activeProject.set({
        ...current,
        buildGuide: guide
      });
      this.saveActiveProjectToDisk();
      this.currentStep.set('guide');
    } catch (err) {
      console.error(err);
      alert('Underbelly stitch guides went offline! Retrying to secure seam maps.');
    } finally {
      this.isGeneratingGuide.set(false);
    }
  }

  // Export & Download Patterns Config file
  exportSewingProject() {
    const proj = this.activeProject();
    if (!proj) return;

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(proj, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `${proj.title.toLowerCase().replace(/\\s+/g, '_')}_patterns.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }
}
