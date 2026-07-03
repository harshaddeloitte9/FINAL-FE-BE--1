import React from "react";
import { jsx } from "react/jsx-runtime";
//#region src/lib/app-context.tsx
var DatasetContext = React.createContext(null);
function DatasetProvider({ children }) {
	const [file, setFile] = React.useState(null);
	const [profile, setProfile] = React.useState(null);
	const [recommendations, setRecommendations] = React.useState(null);
	const [selectedModel, setSelectedModelState] = React.useState(null);
	const [compareModels, setCompareModelsState] = React.useState(null);
	const [preprocessingResult, setPreprocessingResultState] = React.useState(null);
	const [featureEngineeringResult, setFeatureEngineeringResultState] = React.useState(null);
	const [trainingConfig, setTrainingConfigState] = React.useState(null);
	const [trainingResult, setTrainingResultState] = React.useState(null);
	const [comparisonResults, setComparisonResultsState] = React.useState(null);
	const [selectedComparisonModel, setSelectedComparisonModelState] = React.useState(null);
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
			const parsed = JSON.parse(stored);
			if (parsed.trainingConfig) setTrainingConfigState(parsed.trainingConfig);
			if (parsed.trainingResult) setTrainingResultState(parsed.trainingResult);
			if (parsed.comparisonResults) setComparisonResultsState(parsed.comparisonResults);
			if (parsed.compareModels) setCompareModelsState(parsed.compareModels);
			if (parsed.selectedModel) setSelectedModelState(parsed.selectedModel);
			if (parsed.selectedComparisonModel) setSelectedComparisonModelState(parsed.selectedComparisonModel);
		} catch {} finally {
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
			selectedComparisonModel
		};
		window.localStorage.setItem("aegis_dataset_state", JSON.stringify(persisted));
	}, [
		trainingConfig,
		trainingResult,
		comparisonResults,
		compareModels,
		selectedModel,
		selectedComparisonModel,
		isHydrated
	]);
	const setUploadResult = React.useCallback((f, p) => {
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
	const setProfileState = React.useCallback((p) => {
		setProfile(p);
	}, []);
	const setSelectedModel = React.useCallback((model) => {
		setSelectedModelState(model);
	}, []);
	const setCompareModels = React.useCallback((models) => {
		setCompareModelsState(models);
	}, []);
	const setPreprocessingResult = React.useCallback((result) => {
		setPreprocessingResultState(result);
	}, []);
	const setFeatureEngineeringResult = React.useCallback((result) => {
		setFeatureEngineeringResultState(result);
	}, []);
	const setTrainingConfig = React.useCallback((config) => {
		setTrainingConfigState(config);
	}, []);
	const setTrainingResult = React.useCallback((result) => {
		setTrainingResultState(result);
	}, []);
	const setComparisonResults = React.useCallback((results) => {
		setComparisonResultsState(results);
	}, []);
	const setSelectedComparisonModel = React.useCallback((modelName) => {
		setSelectedComparisonModelState(modelName);
	}, []);
	const value = React.useMemo(() => ({
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
		setSelectedComparisonModel
	}), [
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
		setUploadResult,
		setRecommendations,
		setSelectedModel,
		setCompareModels,
		setPreprocessingResult,
		setFeatureEngineeringResult,
		setTrainingConfig,
		setTrainingResult,
		setComparisonResults,
		setSelectedComparisonModel
	]);
	return /* @__PURE__ */ jsx(DatasetContext.Provider, {
		value,
		children
	});
}
function useDataset() {
	const ctx = React.useContext(DatasetContext);
	if (!ctx) throw new Error("useDataset must be used within DatasetProvider");
	return ctx;
}
//#endregion
export { useDataset as n, DatasetProvider as t };
