import React from 'react';
import styled from 'styled-components';
import Modal from 'react-modal';

const ModalContainer = styled(Modal)`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;  
  padding: 24px;
  background-color: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  position: absolute;
  top: 40%;
  left: 50%;
  transform: translate(-50%, -50%);
  max-width: 400px;
  width: 80%;
`;

const ModalTitle = styled.h2`
  font-size: 24px;
  margin-bottom: 16px;
  color: #333;
`;

const ModalContent = styled.p`
  font-size: 16px;
  color: #666;
  margin-bottom: 24px;
  text-align: center;
`;

const ButtonContainer = styled.div`
  display: flex;
  gap: 10px;
`;

const Button = styled.button`
  padding: 12px 16px;
  font-size: 16px;
  font-weight: bold;
  color: white;
  background-color: ${({ color }) => color || '#e53e3e'};
  border: none;
  border-radius: 4px;
  cursor: pointer;
  &:hover {
    background-color: ${({ hoverColor }) => hoverColor || '#c53030'};
  }
`;

const ConfirmModal = ({
  isOpen,
  onRequestClose,
  title,
  content,
  onConfirm,
  closeModal,
  confirmText = '확인',
  cancelText = '닫기',
  confirmColor = '#4aaa87',
  confirmHoverColor = '#3b8b6d',
  cancelColor = '#e53e3e',
  cancelHoverColor = '#c53030'
}) => (
  <ModalContainer
    isOpen={isOpen}
    onRequestClose={onRequestClose}
    contentLabel="Delete Confirmation"
    ariaHideApp={false}
  >
    <ModalTitle>{title}</ModalTitle>
    <ModalContent>{content}</ModalContent>
    <ButtonContainer>
      <Button color={confirmColor} hoverColor={confirmHoverColor} onClick={onConfirm}>
        {confirmText}
      </Button>
      <Button color={cancelColor} hoverColor={cancelHoverColor} onClick={closeModal}>
        {cancelText}
      </Button>
    </ButtonContainer>
  </ModalContainer>
);

export default ConfirmModal;