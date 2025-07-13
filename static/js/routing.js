export const endpoints = {
    inferenceData: '/inference_data',
    snapshots: '/snapshots',
    clearSnapshots: '/clear_snapshots',
    logs: '/logs',
    cameraParams: '/camera_params',
    startTimeLapse: '/start_time_lapse',
    stopTimeLapse: '/stop_time_lapse',
    diagnostics: '/diagnostics',
    setTilt: '/set_tilt',
    getTilt: '/get_tilt',
    plantHeight: '/plant_height'
};

export function init() {
    console.log("Routing loaded");
}