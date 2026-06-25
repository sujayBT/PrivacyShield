import React, { createContext, useState, useContext } from 'react';
import { login as apiLogin, register as apiRegister } from '../api';

export const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [username, setUsername] = useState(() => localStorage.getItem('username'));
  const [loading, setLoading] = useState(false);

  const doLogin = async (user, pass) => {
    setLoading(true);
    try {
      const data = await apiLogin(user, pass);
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('username', user);
      setToken(data.access_token);
      setUsername(user);
    } finally { setLoading(false); }
  };

  // Register ONLY — does NOT auto-login. Caller must navigate to /login.
  const doRegister = async (user, pass) => {
    setLoading(true);
    try {
      await apiRegister(user, pass);
    } finally { setLoading(false); }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('activeScan');
    setToken(null); setUsername(null);
  };

  return (
    <AuthContext.Provider value={{ token, username, loading, isAuth: !!token, doLogin, doRegister, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
