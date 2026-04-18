import gymnasium
from gymnasium import spaces
import numpy as np
import random
import torch
from typing import TypedDict, Any, Dict, Tuple, Optional, Union
from pydantic import BaseModel

class StateDict(TypedDict):
    """Structured typed dictionary for OpenEnv compliance"""
    soc: np.ndarray
    grid_load: np.ndarray
    time: np.ndarray
    arrival_flags: np.ndarray
    time_remaining: np.ndarray

class ActionDict(TypedDict):
    action: np.ndarray

class RewardDict(TypedDict):
    reward: float

class ObservationModel(BaseModel):
    soc: list[float]
    grid_load: list[float]
    time: list[float]
    arrival_flags: list[float]
    time_remaining: list[float]

class ActionModel(BaseModel):
    action: list[float]

class RewardModel(BaseModel):
    reward: float

class Config(TypedDict):
    """Configuration mapping for difficulties"""
    NUM_CHARGERS: int
    MAX_CHARGE_RATE: float
    MIN_CHARGE_RATE: float
    GRID_CAPACITY: float
    TIME_STEPS_PER_DAY: int
    MAX_EPISODE_STEPS: int
    BATTERY_CAPACITY: float
    TARGET_SOC: float
    ELECTRICITY_PRICE_PEAK: float
    ELECTRICITY_PRICE_OFFPEAK: float
    PENALTY_OVERLOAD: float
    PENALTY_UNFINISHED: float
    REWARD_SOC_REACHED: float
    REWARD_SCALE: float
    COST_WEIGHT: float
    SOC_WEIGHT: float
    PENALTY_WEIGHT: float

TASK_CONFIGS: Dict[str, Config] = {
    "easy": {
        "NUM_CHARGERS": 5, "MAX_CHARGE_RATE": 50.0, "MIN_CHARGE_RATE": 0.0,
        "GRID_CAPACITY": 1000.0, "TIME_STEPS_PER_DAY": 24, "MAX_EPISODE_STEPS": 24,
        "BATTERY_CAPACITY": 60.0, "TARGET_SOC": 0.85, "ELECTRICITY_PRICE_PEAK": 0.20,
        "ELECTRICITY_PRICE_OFFPEAK": 0.10, "PENALTY_OVERLOAD": 5.0, "PENALTY_UNFINISHED": 5.0,
        "REWARD_SOC_REACHED": 15.0, "REWARD_SCALE": 0.1, 
        "COST_WEIGHT": 0.3, "SOC_WEIGHT": 25.0, "PENALTY_WEIGHT": 1.0
    },
    "medium": {
        "NUM_CHARGERS": 5, "MAX_CHARGE_RATE": 50.0, "MIN_CHARGE_RATE": 0.0,
        "GRID_CAPACITY": 150.0, "TIME_STEPS_PER_DAY": 24, "MAX_EPISODE_STEPS": 24,
        "BATTERY_CAPACITY": 60.0, "TARGET_SOC": 0.90, "ELECTRICITY_PRICE_PEAK": 0.25,
        "ELECTRICITY_PRICE_OFFPEAK": 0.10, "PENALTY_OVERLOAD": 20.0, "PENALTY_UNFINISHED": 10.0,
        "REWARD_SOC_REACHED": 15.0, "REWARD_SCALE": 0.1,
        "COST_WEIGHT": 0.3, "SOC_WEIGHT": 25.0, "PENALTY_WEIGHT": 2.0
    },
    "hard": {
        "NUM_CHARGERS": 5, "MAX_CHARGE_RATE": 50.0, "MIN_CHARGE_RATE": 0.0,
        "GRID_CAPACITY": 100.0, "TIME_STEPS_PER_DAY": 24, "MAX_EPISODE_STEPS": 24,
        "BATTERY_CAPACITY": 60.0, "TARGET_SOC": 0.95, "ELECTRICITY_PRICE_PEAK": 0.35,
        "ELECTRICITY_PRICE_OFFPEAK": 0.15, "PENALTY_OVERLOAD": 50.0, "PENALTY_UNFINISHED": 20.0,
        "REWARD_SOC_REACHED": 15.0, "REWARD_SCALE": 0.1,
        "COST_WEIGHT": 0.3, "SOC_WEIGHT": 25.0, "PENALTY_WEIGHT": 5.0
    }
}

class EVChargingEnv(gymnasium.Env):
    """
    OpenEnv + Gymnasium compliant RL environment for EV charging load balancing.
    """
    metadata: Dict[str, Any] = {"render_modes": ["human"]}
    
    def __init__(self, difficulty: str = "medium", render_mode: Optional[str] = None):
        super().__init__()
        self.difficulty: str = difficulty
        self.config: Config = TASK_CONFIGS[self.difficulty]
        self.render_mode: Optional[str] = render_mode
        self.num_chargers: int = self.config["NUM_CHARGERS"]
        self.max_rate: float = self.config["MAX_CHARGE_RATE"]
        self.grid_cap: float = self.config["GRID_CAPACITY"]
        self.max_ep_steps: int = self.config["MAX_EPISODE_STEPS"]
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(self.num_chargers,), dtype=np.float32)

        self.observation_space = spaces.Dict({
            "soc": spaces.Box(low=0.0, high=1.0, shape=(self.num_chargers,), dtype=np.float32),
            "grid_load": spaces.Box(low=0.0, high=float('inf'), shape=(1,), dtype=np.float32),
            "time": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
            "arrival_flags": spaces.Box(low=0.0, high=1.0, shape=(self.num_chargers,), dtype=np.float32),
            "time_remaining": spaces.Box(low=0.0, high=1.0, shape=(self.num_chargers,), dtype=np.float32)
        })

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[StateDict, dict]:
        """Resets the environment uniformly ensuring reproducibility"""
        super().reset(seed=seed)
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            self.action_space.seed(seed)
            self.observation_space.seed(seed)
            
        self.current_step: int = 0
        self.total_cost: float = 0.0
        self.total_overload_penalty: float = 0.0
        
        self.soc: np.ndarray = np.zeros(self.num_chargers, dtype=np.float32)
        self.arrival_times: np.ndarray = np.zeros(self.num_chargers, dtype=np.int32)
        self.departure_times: np.ndarray = np.zeros(self.num_chargers, dtype=np.int32)
        self.received_soc_bonus: np.ndarray = np.zeros(self.num_chargers, dtype=bool)
        self.prev_action: Optional[np.ndarray] = None
        
        for i in range(self.num_chargers):
            self.soc[i] = random.uniform(0.1, 0.6)
            self.arrival_times[i] = random.randint(0, 6)
            self.departure_times[i] = random.randint(16, 23)
            
        self.current_grid_load: float = 0.0
        obs = self._get_obs()
        
        ObservationModel(**{k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in obs.items()})
        return obs, self._get_info()
    
    def _get_obs(self) -> StateDict:
        """Constructs strictly typed observation dictionary matching spaces"""
        arrival_flags = np.array(
            [1.0 if self.current_step >= self.arrival_times[i] and self.current_step < self.departure_times[i] else 0.0 for i in range(self.num_chargers)], 
            dtype=np.float32
        )
        time_rem = np.zeros(self.num_chargers, dtype=np.float32)
        for i in range(self.num_chargers):
            if arrival_flags[i] == 1.0:
                time_rem[i] = (self.departure_times[i] - self.current_step) / self.max_ep_steps
                
        return {
            "soc": np.clip(self.soc, 0.0, 1.0).astype(np.float32),
            "grid_load": np.array([self.current_grid_load / self.grid_cap], dtype=np.float32),
            "time": np.array([self.current_step / self.config["TIME_STEPS_PER_DAY"]], dtype=np.float32),
            "arrival_flags": arrival_flags,
            "time_remaining": time_rem
        }

    def state(self) -> StateDict:
        """Strict OpenEnv state exposure requirement"""
        return self._get_obs()

    def _get_info(self) -> Dict[str, Any]:
        """Metrics tracker"""
        return {
            "total_cost": self.total_cost,
            "total_overload_penalty": self.total_overload_penalty,
            "mean_soc": float(np.mean(self.soc)),
            "step": self.current_step
        }

    def step(self, action: Union[np.ndarray, ActionDict]) -> Tuple[StateDict, Union[float, RewardDict], bool, bool, dict]:
        """
        Executes an agent action, calculates physics, steps time forward, and resolves rewards.
        
        OpenEnv Types:
        - Observation = StateDict
        - Action = ActionDict
        - Reward = scalar float wrapped logically
        """
        if isinstance(action, dict):
            action = action["action"]
            
        action_list = action.tolist() if isinstance(action, np.ndarray) else list(action)
        ActionModel(action=action_list)
        
        action = np.clip(action, 0.0, 1.0).astype(np.float32)
            
        charge_rates: np.ndarray = np.array(action, dtype=np.float32) * self.max_rate
        
        arrival_flags: np.ndarray = np.array([1.0 if self.current_step >= self.arrival_times[i] and self.current_step < self.departure_times[i] else 0.0 for i in range(self.num_chargers)], dtype=np.float32)
        charge_rates *= arrival_flags
        
        idle_penalty: float = 0.0
        for i in range(self.num_chargers):
            if arrival_flags[i] == 1.0 and charge_rates[i] < 1.0:
                idle_penalty += 0.1

        smoothness_penalty: float = 0.0
        current_action_array = np.array(action, dtype=np.float32)
        if hasattr(self, 'prev_action') and self.prev_action is not None:
            diff = np.abs(current_action_array - self.prev_action)
            smoothness_penalty = float(np.sum(diff)) * 0.05
        self.prev_action = current_action_array
        
        total_power: float = float(np.sum(charge_rates))
        self.current_grid_load = total_power
        
        is_peak: bool = (8 <= self.current_step < 20)
        price: float = self.config["ELECTRICITY_PRICE_PEAK"] if is_peak else self.config["ELECTRICITY_PRICE_OFFPEAK"]
        cost_this_step: float = total_power * price
        self.total_cost += cost_this_step
        mean_soc_increase: float = 0.0
        bonus_reward: float = 0.0
        for i in range(self.num_chargers):
            if arrival_flags[i] == 1.0:
                added_soc: float = charge_rates[i] / self.config["BATTERY_CAPACITY"]
                self.soc[i] = min(1.0, self.soc[i] + added_soc)
                mean_soc_increase += added_soc
                
                if self.soc[i] >= self.config["TARGET_SOC"] and not self.received_soc_bonus[i]:
                    bonus_reward += self.config["REWARD_SOC_REACHED"] * 0.3
                    self.received_soc_bonus[i] = True

        penalty: float = 0.0
        if total_power > self.grid_cap:
            overload: float = total_power - self.grid_cap
            penalty = self.config["PENALTY_OVERLOAD"] * (overload / self.grid_cap)
            self.total_overload_penalty += penalty
            
        reward: float = -(self.config["COST_WEIGHT"] * cost_this_step * self.config["REWARD_SCALE"]) \
                 + (self.config["SOC_WEIGHT"] * (mean_soc_increase / self.num_chargers)) \
                 - (self.config["PENALTY_WEIGHT"] * penalty) \
                 + bonus_reward \
                 - idle_penalty \
                 - smoothness_penalty
                 
        self.current_step += 1
        terminated: bool = (self.current_step >= self.max_ep_steps)
        truncated: bool = False
        
        if np.all(self.soc >= self.config["TARGET_SOC"]):
            terminated = True
        
        if terminated:
            for i in range(self.num_chargers):
                if self.soc[i] < self.config["TARGET_SOC"]:
                    reward -= self.config["PENALTY_UNFINISHED"] * (self.config["TARGET_SOC"] - self.soc[i])
                    
        obs = self._get_obs()
        for k in obs:
            obs[k] = np.array(obs[k], dtype=np.float32)
            
        reward = float(np.nan_to_num(reward, nan=0.0, posinf=1.0, neginf=-1.0))
        reward_float = float(reward)
        terminated = bool(terminated)
        truncated = bool(truncated)
        
        ObservationModel(**{k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in obs.items()})
        RewardModel(reward=reward_float)
                    
        return obs, reward_float, terminated, truncated, self._get_info()

    def openenv_step(self, action: Union[np.ndarray, ActionDict]) -> Tuple[StateDict, float, bool, dict]:
        """
        OpenEnv compliant step wrapper returning 4-tuple:
        (obs, reward, done, info)
        """
        obs, reward, terminated, truncated, info = self.step(action)
        done = terminated or truncated
        
        ObservationModel(**{k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in obs.items()})
        RewardModel(reward=reward)
        
        return obs, reward, done, info

def grade_agent(cost: float, average_soc: float, overload_penalty: float) -> float:
    """Standardized multi-task judge scoring component mapping evaluations dynamically to [0.0, 1.0]"""
    cost_score: float = max(0.0, 1.0 - (cost / 250.0))
    
    soc_score: float = average_soc / 100.0 if average_soc > 1.0 else average_soc
        
    overload_score: float = max(0.0, 1.0 - overload_penalty)
    
    final_score: float = (0.5 * cost_score) + (0.3 * soc_score) + (0.2 * overload_score)
    return float(np.clip(final_score, 0.0, 1.0))
