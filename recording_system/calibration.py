"""
Camera calibration using OpenCV checkerboard detection.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from rich.console import Console
from rich.prompt import Prompt

import config
from utils import print_section, print_ok, print_warning, print_error, print_info, open_video_capture

console = Console()


# ==================== CALIBRATION WORKFLOW ====================

def calibrate_single_camera(device_index: int, cam_name: str = "Camera") -> Optional[Dict]:
    """
    Run interactive calibration for a single camera using checkerboard pattern.
    
    WORKFLOW:
    1. Show live feed
    2. Wait for user to position checkerboard in view
    3. User presses SPACE to capture frame
    4. Attempt to detect checkerboard corners
    5. If successful, collect frame. If not, prompt to try again.
    6. After 15+ captures, run cv2.calibrateCamera()
    7. Save calibration results to NPZ file
    
    Args:
        device_index: OpenCV VideoCapture device index
        cam_name: friendly name for display
    
    Returns:
        Dict with calibration results or None if failed
    """
    print_section(f"Calibrating {cam_name} (Device {device_index})")
    
    # Open camera
    cap = open_video_capture(device_index)
    if not cap.isOpened():
        print_error(f"Cannot open {cam_name}")
        return None
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.RESOLUTION[1])
    
    # Checkerboard parameters
    pattern_size = config.CHECKERBOARD_SIZE
    square_size = config.CHECKERBOARD_SQUARE_SIZE
    min_frames = config.CALIBRATION_FRAMES_NEEDED
    
    # Prepare object points (0,0,0), (1,0,0), ..., (8,5,0)
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size
    
    # Store all good frames and object points
    objpoints = []  # 3d points in real world space
    imgpoints = []  # 2d points in image plane
    
    captured = 0
    
    print_info(f"Instructions:")
    print_info(f"  1. Position the {pattern_size[0]}x{pattern_size[1]} checkerboard in the camera view")
    print_info(f"  2. Press SPACE to capture frame")
    print_info(f"  3. Repeat from different angles/distances ({min_frames} frames needed)")
    print_info(f"  4. Press ESC when done collecting frames")
    print_info(f"  5. Or press 'Q' to abort")
    
    input("Press ENTER to begin...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print_error("Failed to read frame")
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Try to find checkerboard
        ret_find, corners = cv2.findChessboardCorners(gray, pattern_size, None)
        
        # Display current state
        display_frame = frame.copy()
        
        if ret_find:
            # Draw detected corners
            cv2.drawChessboardCorners(display_frame, pattern_size, corners, ret_find)
            cv2.putText(
                display_frame,
                f"Checkerboard FOUND",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )
        else:
            cv2.putText(
                display_frame,
                f"No checkerboard detected - adjust position",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 165, 255),
                2,
            )
        
        # Show counter
        cv2.putText(
            display_frame,
            f"Captured: {captured}/{min_frames}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0) if captured >= min_frames else (0, 0, 255),
            2,
        )
        
        cv2.putText(
            display_frame,
            "SPACE=Capture, ESC=Done, Q=Abort",
            (10, display_frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        
        cv2.imshow(f"Calibration - {cam_name}", display_frame)
        
        key = cv2.waitKey(30) & 0xFF
        
        if key == ord(' '):  # SPACE - capture
            if ret_find:
                objpoints.append(objp)
                # Refine corner positions
                corners_refined = cv2.cornerSubPix(
                    gray,
                    corners,
                    (11, 11),
                    (-1, -1),
                    (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                )
                imgpoints.append(corners_refined)
                captured += 1
                print_ok(f"Frame {captured} captured")
            else:
                print_warning("No checkerboard detected in current frame")
        
        elif key == 27:  # ESC - done
            if captured >= min_frames:
                print_ok(f"Collected {captured} frames")
                break
            else:
                print_warning(f"Need at least {min_frames} frames, only have {captured}")
        
        elif key == ord('q'):  # Q - abort
            print_error("Calibration aborted")
            cap.release()
            cv2.destroyAllWindows()
            return None
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Run calibration
    print_info("Running calibration...")
    
    ret, camera_matrix, distortion_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints,
        imgpoints,
        gray.shape[::-1],
        None,
        None,
    )
    
    if ret:
        # Calculate reprojection error
        total_error = 0
        total_points = 0
        
        for i in range(len(objpoints)):
            proj_imgpoints, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], camera_matrix, distortion_coeffs)
            error = cv2.norm(imgpoints[i], proj_imgpoints, cv2.NORM_L2) / len(proj_imgpoints)
            total_error += error
            total_points += 1
        
        mean_error = total_error / total_points if total_points > 0 else 0
        
        print_ok(f"Calibration successful!")
        print_ok(f"  RMS reprojection error: {mean_error:.4f} pixels")
        print_ok(f"  Camera matrix shape: {camera_matrix.shape}")
        print_ok(f"  Distortion coeffs shape: {distortion_coeffs.shape}")
        
        return {
            "status": "success",
            "camera_matrix": camera_matrix,
            "distortion_coeffs": distortion_coeffs,
            "mean_error": mean_error,
            "num_frames": len(objpoints),
            "rvecs": rvecs,
            "tvecs": tvecs,
        }
    else:
        print_error("Calibration failed")
        return None


def save_calibration(calib_result: Dict, device_index: int, output_dir: Path = config.CALIBRATION_DIR):
    """
    Save calibration result to NPZ file.
    
    Args:
        calib_result: dict with calibration data
        device_index: camera device index
        output_dir: output directory
    """
    output_file = output_dir / f"cam{device_index}_calibration.npz"
    
    np.savez(
        output_file,
        camera_matrix=calib_result["camera_matrix"],
        distortion_coeffs=calib_result["distortion_coeffs"],
        mean_error=calib_result["mean_error"],
        num_frames=calib_result["num_frames"],
    )
    
    print_ok(f"Calibration saved to {output_file}")


def load_calibration(device_index: int, input_dir: Path = config.CALIBRATION_DIR) -> Optional[Dict]:
    """
    Load previously saved calibration.
    
    Args:
        device_index: camera device index
        input_dir: input directory
    
    Returns:
        Dict with calibration data or None if not found
    """
    input_file = input_dir / f"cam{device_index}_calibration.npz"
    
    if not input_file.exists():
        return None
    
    data = np.load(input_file)
    
    return {
        "camera_matrix": data["camera_matrix"],
        "distortion_coeffs": data["distortion_coeffs"],
        "mean_error": float(data["mean_error"]),
        "num_frames": int(data["num_frames"]),
    }


def run_camera_calibration(webcam_assignments: Dict) -> Dict:
    """
    Run calibration for all 3 webcams.
    
    Args:
        webcam_assignments: dict like {"webcam_1": device_idx, ...}
    
    Returns:
        Dict with results for all cameras
    """
    print_section("CAMERA CALIBRATION")
    
    results = {}
    
    for cam_num in range(1, 4):
        cam_key = f"webcam_{cam_num}"
        device_idx = webcam_assignments.get(cam_key)
        
        if device_idx is None:
            print_warning(f"Webcam {cam_num} not assigned, skipping")
            continue
        
        # Check if already calibrated
        existing = load_calibration(device_idx)
        if existing:
            print_info(f"Webcam {cam_num} already calibrated (mean error: {existing['mean_error']:.4f})")
            use_existing = Prompt.ask(
                f"Use existing calibration?",
                choices=["y", "n"],
                default="y",
            )
            if use_existing.lower() == "y":
                results[cam_key] = existing
                continue
        
        # Run new calibration
        calib_result = calibrate_single_camera(device_idx, f"Webcam {cam_num}")
        
        if calib_result:
            results[cam_key] = calib_result
            save_calibration(calib_result, device_idx)
        else:
            print_error(f"Calibration failed for Webcam {cam_num}")
    
    return results


if __name__ == "__main__":
    # Example: calibrate camera at device index 0
    result = calibrate_single_camera(0, "Test Camera")
    if result:
        save_calibration(result, 0)
