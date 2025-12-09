"""Mock class to simulate buildingspy.io.outputfile.Reader for testing"""
import re
import numpy as np


class MockModelicaReader:
    """Mock class to simulate buildingspy.io.outputfile.Reader for testing"""
    
    def __init__(self, mock_data: dict):
        """
        Args:
            mock_data: Dictionary where keys are variable names and values are lists of data points
                      Example: {"ETot.y": [100, 200, 300], "nBui": [2]}
        """
        self._mock_data = mock_data
        self._time_length = None
        
        # Find the time length from the first non-scalar variable
        for var_name, data in mock_data.items():
            if isinstance(data, list) and len(data) > 1:
                self._time_length = len(data)
                break
    
    def varNames(self, pattern=None):
        """Return list of variable names, optionally filtered by regex pattern"""
        if pattern is None:
            return list(self._mock_data.keys())
        
        # Simple regex matching
        matching_vars = []
        for var_name in self._mock_data.keys():
            if re.search(pattern, var_name):
                matching_vars.append(var_name)
        return matching_vars
    
    def values(self, variable_name):
        """Return (time, values) tuple for a variable"""
        if variable_name not in self._mock_data:
            raise KeyError(f"Variable {variable_name} not found")
        
        data = self._mock_data[variable_name]
        
        # For scalar values (like nBui), return a single time point
        if not isinstance(data, list):
            data = [data]
        
        # Create time array matching the data length
        if len(data) == 1:
            time = np.array([0.0])
        else:
            # Create time array in seconds (0, 3600, 7200, ... for hourly data)
            time = np.array([i * 3600.0 for i in range(len(data))])
        
        return (time, np.array(data))
