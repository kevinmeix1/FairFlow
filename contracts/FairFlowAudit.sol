// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title FairFlowAudit
/// @notice Anchors FairFlow Guardian decision hashes so trade/no-trade reports can be verified later.
contract FairFlowAudit {
    struct Decision {
        address reporter;
        string symbol;
        string action;
        uint64 timestamp;
        string metadataURI;
    }

    mapping(bytes32 => Decision) public decisions;

    event DecisionAnchored(
        bytes32 indexed decisionHash,
        address indexed reporter,
        string symbol,
        string action,
        uint64 timestamp,
        string metadataURI
    );

    error EmptyHash();
    error AlreadyAnchored(bytes32 decisionHash);

    function anchorDecision(
        bytes32 decisionHash,
        string calldata symbol,
        string calldata action,
        string calldata metadataURI
    ) external {
        if (decisionHash == bytes32(0)) revert EmptyHash();
        if (decisions[decisionHash].timestamp != 0) revert AlreadyAnchored(decisionHash);

        uint64 anchoredAt = uint64(block.timestamp);
        decisions[decisionHash] = Decision({
            reporter: msg.sender,
            symbol: symbol,
            action: action,
            timestamp: anchoredAt,
            metadataURI: metadataURI
        });

        emit DecisionAnchored(decisionHash, msg.sender, symbol, action, anchoredAt, metadataURI);
    }

    function isAnchored(bytes32 decisionHash) external view returns (bool) {
        return decisions[decisionHash].timestamp != 0;
    }
}

