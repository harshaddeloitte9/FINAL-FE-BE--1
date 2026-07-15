import React from "react";

type DatasetProfile = Record<string, any>;
type ModelRecommendation = Record<string, any>;

type TrainingConfig = {
  test_size: number;
  val_size: number;
  random_seed: number;
  use_cv: boolean;
  cv_folds: number;
  use_hyperopt: boolean;
  use_class_weight: boolean;
  scale_pos_weight: number;
  use_feature_engineering: boolean;
  manual_params: Record<string, any>;
};

type ComparisonResult = {
  model_name: string;
  roc_auc?: number;
  recall?: number;
  precision?: number;
  f1?: number;
  pr_auc?: number;
  accuracy?: number;
  training_time_s?: number;
};

type TrainingResult = {
  task_type: string;
  model_name: string;
  real_feature_names: string[];
  training_config?: Record<string, any>;
  training_info: Record<string, any>;
  split_stats: Record<string, any>;
  feature_engineering_summary?: Record<string, any> | null;
  evaluation_metrics?: Record<string, any> | null;
  evaluation_data?: Record<string, any> | null;
  model_artifact?: string;
};

type DatasetState = {
  file?: File | null;
  profile?: DatasetProfile | null;
  recommendations?: ModelRecommendation[] | null;
  selectedModel?: ModelRecommendation | null;
  compareModels?: string[] | null;
  preprocessingResult?: Record<string, any> | null;
  featureEngineeringResult?: Record<string, any> | null;
  trainingConfig?: TrainingConfig | null;
  trainingResult?: TrainingResult | null;
  comparisonResults?: ComparisonResult[] | null;
  selectedComparisonModel?: string | null;
  validationIntakeData?: Record<string, any> | null;
  validationMddText?: string | null;
  validationMddMetrics?: Record<string, any> | null;
  validationProfile?: Record<string, any> | null;
  validationResults?: Record<string, any> | null;
  validationStage3Result?: Record<string, any> | null;
  setUploadResult: (file: File | null, profile: DatasetProfile | null) => void;
  setProfile: (profile: DatasetProfile | null) => void;
  setRecommendations: (recommendations: ModelRecommendation[] | null) => void;
  setSelectedModel: (model: ModelRecommendation | null) => void;
  setPreprocessingResult: (result: Record<string, any> | null) => void;
  setFeatureEngineeringResult: (result: Record<string, any> | null) => void;
  setTrainingConfig: (config: TrainingConfig | null) => void;
  setTrainingResult: (result: TrainingResult | null) => void;
  setComparisonResults: (results: ComparisonResult[] | null) => void;
  setSelectedComparisonModel: (modelName: string | null) => void;
  setCompareModels: (models: string[] | null) => void;
  setValidationIntakeData: (data: Record<string, any> | null) => void;
  setValidationMddText: (text: string | null) => void;
  setValidationMddMetrics: (metrics: Record<string, any> | null) => void;
  setValidationProfile: (profile: Record<string, any> | null) => void;
  setValidationResults: (results: Record<string, any> | null) => void;
  setValidationStage3Result: (result: Record<string, any> | null) => void;
};

const DatasetContext = React.createContext<DatasetState | null>(null);

export function DatasetProvider({ children }: { children: React.ReactNode }) {
  const [file, setFile] = React.useState<File | null>(null);
  const [profile, setProfile] = React.useState<DatasetProfile | null>(null);
  const [recommendations, setRecommendations] = React.useState<ModelRecommendation[] | null>(null);
  const [selectedModel, setSelectedModelState] = React.useState<ModelRecommendation | null>(null);
  const [compareModels, setCompareModelsState] = React.useState<string[] | null>(null);
  const [preprocessingResult, setPreprocessingResultState] = React.useState<Record<string, any> | null>(null);
  const [featureEngineeringResult, setFeatureEngineeringResultState] = React.useState<Record<string, any> | null>(null);
  const [trainingConfig, setTrainingConfigState] = React.useState<TrainingConfig | null>(null);
  const [trainingResult, setTrainingResultState] = React.useState<TrainingResult | null>(null);
  const [comparisonResults, setComparisonResultsState] = React.useState<ComparisonResult[] | null>(null);
  const [selectedComparisonModel, setSelectedComparisonModelState] = React.useState<string | null>(null);
  const [validationIntakeData, setValidationIntakeDataState] = React.useState<Record<string, any> | null>(null);
  const [validationMddText, setValidationMddTextState] = React.useState<string | null>(null);
  const [validationMddMetrics, setValidationMddMetricsState] = React.useState<Record<string, any> | null>(null);
  const [validationProfile, setValidationProfileState] = React.useState<Record<string, any> | null>(null);
  const [validationResults, setValidationResultsState] = React.useState<Record<string, any> | null>(null);
  const [validationStage3Result, setValidationStage3ResultState] = React.useState<Record<string, any> | null>(null);
  const [isHydrated, setIsHydrated] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") {
      setIsHydrated(true);
      return;
    }

    try {
      const stored = window.localStorage.getItem("aegis_dataset_state");
      if (!stored) {
        setIsHydrated(true);
        return;
      }

      const parsed = JSON.parse(stored) as {
        trainingConfig?: TrainingConfig | null;
        trainingResult?: TrainingResult | null;
        comparisonResults?: ComparisonResult[] | null;
        compareModels?: string[] | null;
        selectedModel?: ModelRecommendation | null;
        selectedComparisonModel?: string | null;
      };

      if (parsed.trainingConfig) {
        setTrainingConfigState(parsed.trainingConfig);
      }
      if (parsed.trainingResult) {
        setTrainingResultState(parsed.trainingResult);
      }
      if (parsed.comparisonResults) {
        setComparisonResultsState(parsed.comparisonResults);
      }
      if (parsed.compareModels) {
        setCompareModelsState(parsed.compareModels);
      }
      if (parsed.selectedModel) {
        setSelectedModelState(parsed.selectedModel);
      }
      if (parsed.selectedComparisonModel) {
        setSelectedComparisonModelState(parsed.selectedComparisonModel);
      }
    } catch {
      // Ignore invalid stored state
    } finally {
      setIsHydrated(true);
    }
  }, []);

  React.useEffect(() => {
    if (typeof window === "undefined" || !isHydrated) return;

    const persisted = {
      trainingConfig,
      trainingResult,
      comparisonResults,
      compareModels,
      selectedModel,
      selectedComparisonModel,
    };

    window.localStorage.setItem("aegis_dataset_state", JSON.stringify(persisted));
  }, [trainingConfig, trainingResult, comparisonResults, compareModels, selectedModel, selectedComparisonModel, isHydrated]);

  const setUploadResult = React.useCallback((f: File | null, p: DatasetProfile | null) => {
    setFile(f);
    setProfile(p);
    setRecommendations(null);
    setSelectedModelState(null);
    setCompareModelsState(null);
    setPreprocessingResultState(null);
    setFeatureEngineeringResultState(null);
    setTrainingConfigState(null);
    setTrainingResultState(null);
    setComparisonResultsState(null);
    setSelectedComparisonModelState(null);
  }, []);

  const setProfileState = React.useCallback((p: DatasetProfile | null) => {
    setProfile(p);
  }, []);

  const setSelectedModel = React.useCallback((model: ModelRecommendation | null) => {
    setSelectedModelState(model);
  }, []);

  const setCompareModels = React.useCallback((models: string[] | null) => {
    setCompareModelsState(models);
  }, []);

  const setPreprocessingResult = React.useCallback((result: Record<string, any> | null) => {
    setPreprocessingResultState(result);
  }, []);

  const setFeatureEngineeringResult = React.useCallback((result: Record<string, any> | null) => {
    setFeatureEngineeringResultState(result);
  }, []);

  const setTrainingConfig = React.useCallback((config: TrainingConfig | null) => {
    setTrainingConfigState(config);
  }, []);

  const setTrainingResult = React.useCallback((result: TrainingResult | null) => {
    setTrainingResultState(result);
  }, []);

  const setComparisonResults = React.useCallback((results: ComparisonResult[] | null) => {
    setComparisonResultsState(results);
  }, []);

  const setSelectedComparisonModel = React.useCallback((modelName: string | null) => {
    setSelectedComparisonModelState(modelName);
  }, []);

  const setValidationIntakeData = React.useCallback((data: Record<string, any> | null) => {
    setValidationIntakeDataState(data);
  }, []);

  const setValidationMddText = React.useCallback((text: string | null) => {
    setValidationMddTextState(text);
  }, []);

  const setValidationMddMetrics = React.useCallback((metrics: Record<string, any> | null) => {
    setValidationMddMetricsState(metrics);
  }, []);

  const setValidationProfile = React.useCallback((profileState: Record<string, any> | null) => {
    setValidationProfileState(profileState);
  }, []);

  const setValidationResults = React.useCallback((results: Record<string, any> | null) => {
    setValidationResultsState(results);
  }, []);

  const setValidationStage3Result = React.useCallback((result: Record<string, any> | null) => {
    setValidationStage3ResultState(result);
  }, []);

  const value = React.useMemo(
    () => ({
      file,
      profile,
      recommendations,
      selectedModel,
      compareModels,
      preprocessingResult,
      featureEngineeringResult,
      trainingConfig,
      trainingResult,
      comparisonResults,
      selectedComparisonModel,
      validationIntakeData,
      validationMddText,
      validationMddMetrics,
      validationProfile,
      validationResults,
      validationStage3Result,
      setUploadResult,
      setProfile: setProfileState,
      setRecommendations,
      setSelectedModel,
      setCompareModels,
      setPreprocessingResult,
      setFeatureEngineeringResult,
      setTrainingConfig,
      setTrainingResult,
      setComparisonResults,
      setSelectedComparisonModel,
      setValidationIntakeData,
      setValidationMddText,
      setValidationMddMetrics,
      setValidationProfile,
      setValidationResults,
      setValidationStage3Result,
    }),
    [
      file,
      profile,
      recommendations,
      selectedModel,
      compareModels,
      preprocessingResult,
      featureEngineeringResult,
      trainingConfig,
      trainingResult,
      comparisonResults,
      selectedComparisonModel,
      validationIntakeData,
      validationMddText,
      validationMddMetrics,
      validationProfile,
      validationResults,
      validationStage3Result,
      setUploadResult,
      setRecommendations,
      setSelectedModel,
      setCompareModels,
      setPreprocessingResult,
      setFeatureEngineeringResult,
      setTrainingConfig,
      setTrainingResult,
      setComparisonResults,
      setSelectedComparisonModel,
      setValidationIntakeData,
      setValidationMddText,
      setValidationMddMetrics,
      setValidationProfile,
      setValidationResults,
      setValidationStage3Result,
    ],
  );

  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

export function useDataset() {
  const ctx = React.useContext(DatasetContext);
  if (!ctx) throw new Error("useDataset must be used within DatasetProvider");
  return ctx;
}

export default DatasetContext;
