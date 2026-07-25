"""cerebro.meta_optimizer — análise + recomendações pro relatório Meta Ads."""

from cerebro.meta_optimizer.config import Config
from cerebro.meta_optimizer.mapper import map_api_to_optimizer
from cerebro.meta_optimizer.optimizer import MetaOptimizer
from cerebro.meta_optimizer.rules import Action

__all__ = ["MetaOptimizer", "map_api_to_optimizer", "Action", "Config"]
