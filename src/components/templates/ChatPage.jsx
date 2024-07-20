import React, { useState, useEffect, useRef } from 'react';
import styled, { css } from 'styled-components';
import { useParams, useLocation, useNavigate } from 'react-router-dom'; // useNavigate 임포트
import { fetchChatHistory, sendChatMessage } from '../../apis/chat';
import SyncLoader from 'react-spinners/SyncLoader';
import { IoMenu } from "react-icons/io5";

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background-color: #ffffff;
  box-sizing: border-box;
  overflow: hidden;
  padding-bottom: 70px;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: center; /* 중앙 정렬 */
  padding: 16px;
  background-color: #4AAA87;
  color: white;
  font-size: 20px;
  font-weight: bold;
  position: relative;

  @media (max-width: 768px) {
    font-size: 18px;
    padding: 12px;
  }
`;

const Title = styled.div`
  flex: 1; /* flex를 사용하여 중앙에 배치 */
  text-align: center; /* 텍스트 중앙 정렬 */
`;

const ChatListButton = styled.button`
  position: absolute; /* 절대 위치 */
  left: 5px; /* 오른쪽에 배치 */
  padding: 10px 12px;
  flex: 1;
  font-weight: 600;
  color: white;
  background-color: #4AAA87;
  border: none;
  border-radius: 20px;
  cursor: pointer;

`;

const ChatBox = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: 16px;
  background-color: #E6F8E0;
  overflow-y: auto;
`;

const MessageList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`;

const MessageContainer = styled.li`
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
  justify-content: ${({ isUser }) => (isUser ? 'flex-end' : 'flex-start')};

  @media (max-width: 768px) {
    margin-bottom: 8px;
  }
`;

const Message = styled.div`
  max-width: 70%;
  display: flex;
  flex-direction: column;
  align-items: ${({ isUser }) => (isUser ? 'flex-end' : 'flex-start')};
  padding: 10px 14px;
  border-radius: 20px;
  background-color: ${({ isUser }) => (isUser ? '#F7FE2E' : 'white')};
  position: relative;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.1);
  word-break: break-word;
  margin-top: 8px;

  @media (max-width: 768px) {
    padding: 8px 10px;
  }
`;

const MessageText = styled.div`
  flex: 1;
`;

const MessageTime = styled.small`
  margin-top: 4px;
  font-size: 0.8em;
  color: #666;
  ${({ isUser }) => isUser ? css`align-self: flex-end;` : css`align-self: flex-start;`}
`;

const ProfileImage = styled.img`
  width: 50px;
  height: 50px;
  border-radius: 50%;
  margin-right: ${({ isUser }) => (isUser ? '0' : '10px')};
  margin-left: ${({ isUser }) => (isUser ? '10px' : '0')};

  @media (max-width: 768px) {
    width: 40px;
    height: 40px;
    margin-right: ${({ isUser }) => (isUser ? '0' : '6px')};
    margin-left: ${({ isUser }) => (isUser ? '6px' : '0')};
  }
`;

const InputBox = styled.form`
  display: flex;
  padding: 20px; /* Increased padding */
  background-color: #f0f0f0;
  border-top: 1px solid #ddd;
  width: 100%;
  box-sizing: border-box;
  position: fixed;
  bottom: 60px; /* Adjust this value to the height of your bottom navigation bar */
  left: 0;
  right: 0;

  @media (max-width: 768px) {
    padding: 16px; /* Increased padding */
  }
`;

const Input = styled.input`
  flex: 1;
  padding: 20px; /* Increased padding */
  border: 1px solid #ddd;
  border-radius: 20px;
  margin-right: 8px;
  font-size: 16px;
  &:focus {
    outline: none;
    border-color: #4aaa87;
  }

  @media (max-width: 768px) {
    padding: 16px; /* Increased padding */
    margin-right: 4px;
  }
`;

const Button = styled.button`
  padding: 10px 16px;
  font-size: 14px;
  color: white;
  background-color: #4aaa87;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  &:hover {
    background-color: #6dc4b0;
  }

  @media (max-width: 768px) {
    padding: 8px 12px;
    font-size: 12px;
  }
`;

const ChatPage = () => {
  const { sessionid } = useParams();
  const location = useLocation();
  const navigate = useNavigate(); // useNavigate 훅 사용
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(sessionid);

  const chatBoxRef = useRef(null);

  const params = new URLSearchParams(location.search);
  const sessionName = params.get('session_name');
  const isLoggedIn = localStorage.getItem('userId') !== null;

  useEffect(() => {
    if (isLoggedIn) {
      localStorage.setItem('sessionId', sessionId);
      localStorage.setItem('sessionName', sessionName);
      const fetchHistory = async () => {
        try {
          const response = await fetchChatHistory(sessionId);
          const orderedMessages = response.data.flatMap(chat => [
            { isUser: true, text: chat.question, timestamp: chat.timestamp },
            { isUser: false, text: chat.answer, timestamp: chat.timestamp }
          ]);
          setMessages([{ isUser: false, text: '안녕하세요 무엇을 도와드릴까요?', timestamp: new Date().toISOString() }, ...orderedMessages]);
        } catch (error) {
          console.error('Error fetching chat history:', error);
        }
      };

      fetchHistory();
    } else {
      setMessages([{ isUser: false, text: '안녕하세요 무엇을 도와드릴까요?', timestamp: new Date().toISOString() }]);
    }
  }, [sessionId, sessionName, isLoggedIn]);

  useEffect(() => {
    if (chatBoxRef.current) {
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const userMessage = {
      isUser: true,
      text: inputValue,
      timestamp: new Date().toISOString()
    };
    setMessages([...messages, userMessage]);
    setInputValue(''); // Clear input field immediately
    setLoading(true);

    const messageData = {
      question: inputValue,
      session_id: sessionId,
      session_name: sessionName,
      user_id: isLoggedIn ? localStorage.getItem('userId') : null
    };

    try {
      const response = await sendChatMessage(messageData);
      const botMessage = {
        isUser: false,
        text: response.data.answer,
        timestamp: response.data.timestamp
      };
      setMessages((prevMessages) => [...prevMessages, botMessage]);
    } catch (error) {
      console.error('Error during chat processing:', error);
      const errorMessage = {
        isUser: false,
        text: 'An error occurred. Please try again later.',
        timestamp: new Date().toISOString()
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container>
      <Header>
        <Title>{sessionName || '농업 GPT'}</Title>
        <ChatListButton onClick={() => navigate('/chatlist')}><IoMenu />  목록 보기</ChatListButton> 
      </Header>
      <ChatBox ref={chatBoxRef}>
        <MessageList>
          {messages.map((msg, index) => (
            <MessageContainer key={index} isUser={msg.isUser}>
              {!msg.isUser && <ProfileImage src={`${process.env.PUBLIC_URL}/android-chrome-192x192.png`} alt="Profile" />}
              <Message isUser={msg.isUser}>
                <MessageText>
                  {!msg.isUser ? (
                    <div dangerouslySetInnerHTML={{ __html: msg.text }} />
                  ) : (
                    <>
                      {msg.text}
                      <br/>
                    </>
                  )}
                </MessageText>
                <MessageTime isUser={msg.isUser}>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</MessageTime>
              </Message>
              {msg.isUser && <ProfileImage src={`${process.env.PUBLIC_URL}/user_icon.jpg`} alt="Profile" isUser />}
            </MessageContainer>
          ))}
          {loading && (
            <MessageContainer isUser={false}>
              <ProfileImage src={`${process.env.PUBLIC_URL}/android-chrome-192x192.png`} alt="Profile" />
              <Message isUser={false} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span>답변을 불러오는 중입니다.</span>
                  <SyncLoader
                    color="#75e781"
                    loading={loading}
                    margin={2}
                    size={8}
                    speedMultiplier={0.7}
                    style={{ marginLeft: '10px' }} // Add some spacing between text and loader
                  />
                </div>
              </Message>
            </MessageContainer>
          )}
        </MessageList>
      </ChatBox>
      <InputBox onSubmit={handleSubmit}>
        <Input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="질문을 입력하세요"
          required
        />
        <Button type="submit">전송</Button>
      </InputBox>
    </Container>
  );
};

export default ChatPage;
